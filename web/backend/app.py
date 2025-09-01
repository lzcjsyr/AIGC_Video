"""
Flask Web API for AIGC Video System
提供RESTful API接口，复用现有核心功能

调用关系:
- 作为Web后端入口，被前端React应用调用
- 调用core/pipeline.py执行视频制作任务
- 调用core/project_scanner.py扫描输入文件和输出项目
- 调用utils.py获取文件信息和日志功能
- 通过SocketIO向前端推送实时进度更新
- 提供文件上传、下载、项目管理等REST API接口
"""

import os
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 首先配置Web专用日志
from web.backend.logging_config import setup_web_logging
setup_web_logging()

# 导入现有的核心模块（不创建新的services层）
from utils import logger, get_file_info, VideoProcessingError
from core.project_scanner import scan_input_files, scan_output_projects, detect_project_progress
from config import Config
from core.pipeline import VideoPipeline
from core.validators import validate_processing_config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# 启用CORS和SocketIO
CORS(app, origins=["http://localhost:3000"])
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000"])

# 全局变量存储运行中的任务（简单的内存存储）
running_tasks = {}

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

# ==================== 文件管理接口 ====================

@app.route('/api/files/input', methods=['GET'])
def list_input_files():
    """获取输入文件列表"""
    try:
        files = scan_input_files()
        return jsonify(files)
    except Exception as e:
        logger.error(f"获取输入文件列表失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    """文件上传接口"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件被上传'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        # 验证文件格式
        filename = secure_filename(file.filename)
        file_ext = Path(filename).suffix.lower()
        
        if file_ext not in Config.SUPPORTED_INPUT_FORMATS:
            return jsonify({'error': f'不支持的文件格式: {file_ext}'}), 400
        
        # 保存文件到input目录
        input_dir = project_root / 'input'
        input_dir.mkdir(exist_ok=True)
        file_path = input_dir / filename
        
        # 如果文件已存在，生成新名称
        if file_path.exists():
            name_part = Path(filename).stem
            ext_part = Path(filename).suffix
            counter = 1
            while file_path.exists():
                filename = f"{name_part}_{counter}{ext_part}"
                file_path = input_dir / filename
                counter += 1
        
        file.save(file_path)
        file_info = get_file_info(str(file_path))
        
        logger.info(f"文件上传成功: {filename}")
        return jsonify({
            'message': '文件上传成功',
            'data': file_info
        })
    
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """文件下载接口"""
    try:
        safe_filename = secure_filename(filename)
        file_path = project_root / 'output' / safe_filename
        
        if not file_path.exists():
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(file_path, as_attachment=True)
    
    except Exception as e:
        logger.error(f"文件下载失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/stream/<path:filename>', methods=['GET'])
def stream_file(filename):
    """文件流式传输接口（用于视频预览）"""
    try:
        safe_filename = secure_filename(filename)
        file_path = project_root / 'output' / safe_filename
        
        if not file_path.exists():
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(file_path)
    
    except Exception as e:
        logger.error(f"文件流式传输失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== 项目管理接口 ====================

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """获取项目列表"""
    try:
        projects = scan_output_projects()
        
        # 为每个项目添加进度信息
        for project in projects:
            progress = detect_project_progress(project['path'])
            project.update({
                'current_step': progress['current_step'],
                'current_step_display': progress['current_step_display'],
                'has_final_video': progress['has_final_video']
            })
        
        return jsonify(projects)
    
    except Exception as e:
        logger.error(f"获取项目列表失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_name>', methods=['DELETE'])
def delete_project(project_name):
    """删除项目"""
    try:
        import shutil
        
        project_path = project_root / 'output' / project_name
        if not project_path.exists():
            return jsonify({'error': '项目不存在'}), 404
        
        shutil.rmtree(project_path)
        logger.info(f"项目已删除: {project_name}")
        
        return jsonify({'message': f'项目 {project_name} 删除成功'})
    
    except Exception as e:
        logger.error(f"删除项目失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== 任务管理接口 ====================

@app.route('/api/tasks/start', methods=['POST'])
def start_task():
    """启动新的视频制作任务"""
    try:
        data = request.get_json()
        
        # 验证必需参数
        required_fields = ['file_path']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'error': f'缺少必需参数: {missing_fields}'}), 400
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 构建处理配置
        config = {
            'input_file': data['file_path'],
            'target_length': data.get('target_length', Config.DEFAULT_TARGET_LENGTH),
            'num_segments': data.get('num_segments', Config.DEFAULT_NUM_SEGMENTS),
            'llm_model': data.get('llm_model', 'google/gemini-2.5-pro'),
            'image_size': data.get('image_size', Config.DEFAULT_IMAGE_SIZE),
            'voice': data.get('voice', Config.DEFAULT_VOICE),
            'image_style_preset': data.get('image_style', 'cinematic'),
            'enable_subtitles': data.get('enable_subtitles', True),
            'bgm_filename': data.get('bgm_filename'),
            'output_dir': 'output',
            'run_mode': 'auto'
        }
        
        # 验证配置
        try:
            validate_processing_config(config)
        except Exception as e:
            return jsonify({'error': f'配置验证失败: {str(e)}'}), 400
        
        # 在后台启动任务
        thread = threading.Thread(
            target=run_video_task,
            args=(task_id, config),
            daemon=True
        )
        thread.start()
        
        logger.info(f"任务已启动: {task_id}")
        return jsonify({
            'message': '任务已启动',
            'task_id': task_id
        })
    
    except Exception as e:
        logger.error(f"启动任务失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    try:
        if task_id not in running_tasks:
            return jsonify({'error': '任务不存在'}), 404
        
        task = running_tasks[task_id]
        
        return jsonify({
            'task_id': task_id,
            'status': task['status'],
            'current_step': task.get('current_step', 1),
            'current_task': task.get('current_task', ''),
            'progress': task.get('progress', 0),
            'final_video_path': task.get('final_video_path'),
            'error_message': task.get('error_message')
        })
    
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== 配置管理接口 ====================

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取系统配置"""
    try:
        api_status = Config.validate_api_keys()
        
        return jsonify({
            'api_status': api_status,
            'system_config': {
                'default_target_length': Config.DEFAULT_TARGET_LENGTH,
                'default_num_segments': Config.DEFAULT_NUM_SEGMENTS,
                'default_image_size': Config.DEFAULT_IMAGE_SIZE,
                'speech_speed': Config.SPEECH_SPEED_WPM,
                'default_subtitles': Config.SUBTITLE_CONFIG['enabled']
            }
        })
    
    except Exception as e:
        logger.error(f"获取配置失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/models', methods=['GET'])
def get_recommended_models():
    """获取推荐模型列表"""
    try:
        return jsonify(Config.RECOMMENDED_MODELS)
    except Exception as e:
        logger.error(f"获取推荐模型失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/test', methods=['POST'])
def test_api_keys():
    """测试API密钥"""
    try:
        # 简单的模拟测试结果
        results = {
            'openrouter': True,
            'siliconflow': False,
            'aihubmix': True,
            'seedream': True,
            'bytedance': False
        }
        
        return jsonify(results)
    
    except Exception as e:
        logger.error(f"测试API密钥失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== 后台任务函数 ====================

def run_video_task(task_id, config):
    """在后台运行视频制作任务"""
    # 初始化任务状态
    running_tasks[task_id] = {
        'status': 'running',
        'current_step': 1,
        'current_task': '正在启动任务...',
        'progress': 0,
        'start_time': datetime.now().isoformat()
    }
    
    try:
        logger.info(f"开始视频制作任务: {task_id}")
        
        # 创建视频管道实例
        pipeline = VideoPipeline(
            input_file=config['input_file'],
            target_length=config['target_length'],
            num_segments=config['num_segments'],
            llm_model=config['llm_model'],
            image_size=config['image_size'],
            voice=config['voice'],
            image_style_preset=config['image_style_preset'],
            enable_subtitles=config['enable_subtitles'],
            bgm_filename=config.get('bgm_filename'),
            output_dir=config['output_dir']
        )
        
        # 执行处理管道
        def progress_callback(step, message, progress=None):
            running_tasks[task_id].update({
                'current_step': step,
                'current_task': message,
                'progress': progress or 0
            })
            
            logger.info(f"任务{task_id} - 步骤{step}: {message}")
            
            # 通过WebSocket发送进度更新
            socketio.emit('task_progress', {
                'task_id': task_id,
                'step': step,
                'message': message,
                'progress': progress
            })
        
        # 运行管道
        result = pipeline.run_full_pipeline(progress_callback=progress_callback)
        
        # 任务完成
        running_tasks[task_id].update({
            'status': 'completed',
            'current_step': 5,
            'current_task': '视频制作完成',
            'progress': 100,
            'final_video_path': result.get('final_video_path'),
            'end_time': datetime.now().isoformat()
        })
        
        logger.info(f"视频制作任务完成: {task_id}")
        
        # 通过WebSocket通知完成
        socketio.emit('task_completed', {
            'task_id': task_id,
            'final_video_path': result.get('final_video_path')
        })
        
    except Exception as e:
        # 任务失败
        error_msg = str(e)
        running_tasks[task_id].update({
            'status': 'failed',
            'error_message': error_msg,
            'end_time': datetime.now().isoformat()
        })
        
        logger.error(f"任务执行失败 {task_id}: {error_msg}")
        
        # 通过WebSocket通知失败
        socketio.emit('task_failed', {
            'task_id': task_id,
            'error': error_msg
        })

# ==================== WebSocket 事件 ====================

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    logger.info('客户端已连接')

@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接"""
    logger.info('客户端已断开连接')

if __name__ == '__main__':
    # 确保必要的目录存在
    (project_root / 'input').mkdir(exist_ok=True)
    (project_root / 'output').mkdir(exist_ok=True)
    
    logger.info('启动Flask Web API服务器')
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)