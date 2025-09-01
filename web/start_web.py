#!/usr/bin/env python3
"""
Web版启动脚本
同时启动前端开发服务器和后端Flask API服务器
"""

import os
import sys
import time
import subprocess
import threading
from pathlib import Path

def start_backend():
    """启动Flask后端服务器"""
    print("🚀 启动后端服务器...")
    backend_dir = Path(__file__).parent / 'backend'
    
    try:
        # 切换到后端目录
        os.chdir(backend_dir)
        
        # 启动Flask应用
        subprocess.run([sys.executable, 'app.py'], check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 后端服务器启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("⏹️ 后端服务器已停止")

def start_frontend():
    """启动Vue前端开发服务器"""
    print("🎨 启动前端开发服务器...")
    frontend_dir = Path(__file__).parent / 'frontend'
    
    try:
        # 切换到前端目录
        os.chdir(frontend_dir)
        
        # 检查是否已安装依赖
        if not (frontend_dir / 'node_modules').exists():
            print("📦 安装前端依赖...")
            subprocess.run(['npm', 'install'], check=True)
        
        # 启动开发服务器
        subprocess.run(['npm', 'run', 'dev'], check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 前端服务器启动失败: {e}")
        print("请确保已安装 Node.js 和 npm")
        sys.exit(1)
    except KeyboardInterrupt:
        print("⏹️ 前端服务器已停止")

def main():
    """主函数"""
    print("🌟 智能视频制作系统 - Web版")
    print("=" * 50)
    
    # 检查必要的目录
    web_dir = Path(__file__).parent
    backend_dir = web_dir / 'backend'
    frontend_dir = web_dir / 'frontend'
    
    if not backend_dir.exists():
        print("❌ 后端目录不存在!")
        sys.exit(1)
    
    if not frontend_dir.exists():
        print("❌ 前端目录不存在!")
        sys.exit(1)
    
    try:
        # 在后台启动后端服务器
        backend_thread = threading.Thread(target=start_backend, daemon=True)
        backend_thread.start()
        
        # 等待后端启动
        print("⏳ 等待后端服务器启动...")
        time.sleep(3)
        
        # 启动前端服务器（主线程）
        start_frontend()
        
    except KeyboardInterrupt:
        print("\n👋 服务器已停止，感谢使用!")
        sys.exit(0)

if __name__ == '__main__':
    main()