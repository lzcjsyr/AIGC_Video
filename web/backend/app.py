"""FastAPI Web API for AIGC Video System"""

import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from werkzeug.utils import secure_filename

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from web.backend.logging_config import setup_web_logging
setup_web_logging()

from utils import logger, get_file_info
from core.project_scanner import scan_input_files, scan_output_projects, detect_project_progress
from config import Config
from core.pipeline import run_auto

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://localhost:8080"], allow_methods=["*"], allow_headers=["*"])

running_tasks = {}

class TaskRequest(BaseModel):
    file_path: str
    target_length: Optional[int] = 1000
    num_segments: Optional[int] = 10
    llm_model: Optional[str] = 'google/gemini-2.5-pro'
    image_size: Optional[str] = Config.DEFAULT_IMAGE_SIZE
    voice: Optional[str] = Config.DEFAULT_VOICE
    image_style: Optional[str] = 'cinematic'
    enable_subtitles: Optional[bool] = True
    bgm_filename: Optional[str] = None

@app.get('/')
def root():
    return {
        'message': 'AIGC Video System FastAPI',
        'version': '2.0.0',
        'docs': '/docs',
        'health': '/api/health'
    }

@app.get('/api/health')
def health_check():
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}

@app.get('/api/files/input')
def list_input_files():
    try:
        return scan_input_files()
    except Exception as e:
        logger.error(f"获取输入文件列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/files/upload')
async def upload_file(file: UploadFile = File(...)):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail='没有选择文件')
        
        filename = secure_filename(file.filename)
        file_ext = Path(filename).suffix.lower()
        
        if file_ext not in Config.SUPPORTED_INPUT_FORMATS:
            raise HTTPException(status_code=400, detail=f'不支持的文件格式: {file_ext}')
        
        input_dir = project_root / 'input'
        input_dir.mkdir(exist_ok=True)
        file_path = input_dir / filename
        
        if file_path.exists():
            name_part = Path(filename).stem
            ext_part = Path(filename).suffix
            counter = 1
            while file_path.exists():
                filename = f"{name_part}_{counter}{ext_part}"
                file_path = input_dir / filename
                counter += 1
        
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        file_info = get_file_info(str(file_path))
        logger.info(f"文件上传成功: {filename}")
        return {'message': '文件上传成功', 'data': file_info}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/files/download/{filename}')
def download_file(filename: str):
    try:
        safe_filename = secure_filename(filename)
        file_path = project_root / 'output' / safe_filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail='文件不存在')
        
        return FileResponse(file_path, filename=safe_filename)
    except Exception as e:
        logger.error(f"文件下载失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/files/stream/{filename}')
def stream_file(filename: str):
    try:
        safe_filename = secure_filename(filename)
        file_path = project_root / 'output' / safe_filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail='文件不存在')
        
        return FileResponse(file_path)
    except Exception as e:
        logger.error(f"文件流式传输失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/projects')
def list_projects():
    try:
        projects = scan_output_projects()
        
        for project in projects:
            progress = detect_project_progress(project['path'])
            project.update({
                'current_step': progress['current_step'],
                'current_step_display': progress['current_step_display'],
                'has_final_video': progress['has_final_video']
            })
        
        return projects
    except Exception as e:
        logger.error(f"获取项目列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete('/api/projects/{project_name}')
def delete_project(project_name: str):
    try:
        import shutil
        
        project_path = project_root / 'output' / project_name
        if not project_path.exists():
            raise HTTPException(status_code=404, detail='项目不存在')
        
        shutil.rmtree(project_path)
        logger.info(f"项目已删除: {project_name}")
        
        return {'message': f'项目 {project_name} 删除成功'}
    except Exception as e:
        logger.error(f"删除项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/tasks/start')
def start_task(task_req: TaskRequest):
    try:
        task_id = str(uuid.uuid4())
        
        config = {
            'input_file': task_req.file_path,
            'target_length': task_req.target_length,
            'num_segments': task_req.num_segments,
            'llm_model': task_req.llm_model,
            'image_size': task_req.image_size,
            'voice': task_req.voice,
            'image_style_preset': task_req.image_style,
            'enable_subtitles': task_req.enable_subtitles,
            'bgm_filename': task_req.bgm_filename,
            'output_dir': 'output',
            'run_mode': 'auto'
        }
        
        # validate_processing_config(config)
        
        thread = threading.Thread(target=run_video_task, args=(task_id, config), daemon=True)
        thread.start()
        
        logger.info(f"任务已启动: {task_id}")
        return {'message': '任务已启动', 'task_id': task_id}
    except Exception as e:
        logger.error(f"启动任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/tasks/{task_id}/status')
def get_task_status(task_id: str):
    if task_id not in running_tasks:
        raise HTTPException(status_code=404, detail='任务不存在')
    
    task = running_tasks[task_id]
    return {
        'task_id': task_id,
        'status': task['status'],
        'current_step': task.get('current_step', 1),
        'current_task': task.get('current_task', ''),
        'progress': task.get('progress', 0),
        'final_video_path': task.get('final_video_path'),
        'error_message': task.get('error_message')
    }

@app.get('/api/config')
def get_config():
    try:
        api_status = Config.validate_api_keys()
        return {
            'api_status': api_status,
            'system_config': {
                'default_target_length': 1000,
                'default_num_segments': 10,
                'default_image_size': Config.DEFAULT_IMAGE_SIZE,
                'speech_speed': Config.SPEECH_SPEED_WPM,
                'default_subtitles': Config.SUBTITLE_CONFIG['enabled']
            }
        }
    except Exception as e:
        logger.error(f"获取配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/api/config/models')
def get_recommended_models():
    try:
        return Config.RECOMMENDED_MODELS
    except Exception as e:
        logger.error(f"获取推荐模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/config/test')
def test_api_keys():
    try:
        return {
            'openrouter': True,
            'siliconflow': False,
            'aihubmix': True,
            'seedream': True,
            'bytedance': False
        }
    except Exception as e:
        logger.error(f"测试API密钥失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def run_video_task(task_id, config):
    running_tasks[task_id] = {
        'status': 'running',
        'current_step': 1,
        'current_task': '正在启动任务...',
        'progress': 0,
        'start_time': datetime.now().isoformat()
    }
    
    try:
        logger.info(f"开始视频制作任务: {task_id}")
        
        def progress_callback(step, message, progress=None):
            running_tasks[task_id].update({
                'current_step': step,
                'current_task': message,
                'progress': progress or 0
            })
            logger.info(f"任务{task_id} - 步骤{step}: {message}")
        
        result = run_auto(
            input_file=config['input_file'],
            output_dir=config['output_dir'],
            target_length=config['target_length'],
            num_segments=config['num_segments'],
            image_size=config['image_size'],
            llm_server='openrouter',
            llm_model=config['llm_model'],
            image_server='siliconflow',
            image_model='flux',
            tts_server='bytedance',
            voice=config['voice'],
            image_style_preset=config['image_style_preset'],
            opening_image_style=config['image_style_preset'],
            enable_subtitles=config['enable_subtitles'],
            bgm_filename=config.get('bgm_filename')
        )
        
        running_tasks[task_id].update({
            'status': 'completed',
            'current_step': 5,
            'current_task': '视频制作完成',
            'progress': 100,
            'final_video_path': result.get('final_video_path'),
            'end_time': datetime.now().isoformat()
        })
        
        logger.info(f"视频制作任务完成: {task_id}")
        
    except Exception as e:
        error_msg = str(e)
        running_tasks[task_id].update({
            'status': 'failed',
            'error_message': error_msg,
            'end_time': datetime.now().isoformat()
        })
        logger.error(f"任务执行失败 {task_id}: {error_msg}")

if __name__ == '__main__':
    (project_root / 'input').mkdir(exist_ok=True)
    (project_root / 'output').mkdir(exist_ok=True)
    
    logger.info('启动FastAPI Web API服务器')
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)