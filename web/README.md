# AIGC Video Web 版本

基于 Vue3 + Flask 的前后端分离Web版本，提供可视化界面来使用智能视频制作系统。

## 架构说明

- **前端**: Vue3 + Element Plus + Vite
- **后端**: Flask + SocketIO + CORS
- **通信**: RESTful API + WebSocket实时通信
- **复用**: 完全复用现有的 `core/` 核心模块

## 功能特性

### 前端界面
- 📁 **文件上传页面**: 支持拖拽上传PDF/EPUB等文档
- ⚙️ **参数配置**: 可视化配置目标字数、分段数、模型选择等
- 📊 **实时进度**: WebSocket实时显示任务执行进度
- 📋 **项目管理**: 查看历史项目，支持重新执行任意步骤
- 🎬 **结果预览**: 在线预览和下载生成的视频
- 🔧 **系统配置**: API密钥配置和系统参数设置

### 后端API
- 🌐 **RESTful接口**: 统一的API设计
- 📤 **文件服务**: 上传、下载、流式传输
- 🔄 **任务管理**: 异步任务执行和状态查询
- 📡 **实时通信**: WebSocket推送任务进度和日志
- 🔌 **核心复用**: 直接调用现有核心功能

## 快速开始

### 环境要求
- Python 3.8+
- Node.js 16+
- npm 或 yarn

### 1. 安装后端依赖
```bash
cd web/backend
pip install -r requirements.txt
```

### 2. 安装前端依赖
```bash
cd web/frontend
npm install
```

### 3. 启动服务（推荐）
在项目的 `web/` 目录下运行：
```bash
python start_web.py
```

这个脚本会自动：
- 启动 Flask 后端服务器 (http://localhost:5000)
- 启动 Vue 前端开发服务器 (http://localhost:3000)
- 配置代理，前端API请求自动转发到后端

### 4. 手动分别启动（开发模式）

**启动后端**:
```bash
cd web/backend
python app.py
```
后端将运行在 http://localhost:5000

**启动前端**:
```bash
cd web/frontend
npm run dev
```
前端将运行在 http://localhost:3000

## API接口文档

### 文件管理
- `GET /api/files/input` - 获取输入文件列表
- `POST /api/files/upload` - 上传文件
- `GET /api/files/download/<filename>` - 下载文件
- `GET /api/files/stream/<filename>` - 流式传输（视频预览）

### 项目管理
- `GET /api/projects` - 获取项目列表
- `DELETE /api/projects/<name>` - 删除项目

### 任务管理
- `POST /api/tasks/start` - 启动新任务
- `POST /api/tasks/rerun` - 重新执行任务
- `GET /api/tasks/<id>/status` - 查询任务状态
- `POST /api/tasks/<id>/retry` - 重试失败任务

### 配置管理
- `GET /api/config` - 获取系统配置
- `GET /api/config/models` - 获取推荐模型列表
- `POST /api/config/api` - 保存API配置
- `POST /api/config/test` - 测试API连接
- `POST /api/config/system` - 保存系统配置

### WebSocket事件
- `task_progress` - 任务进度更新
- `task_log` - 实时日志
- `task_completed` - 任务完成通知
- `task_failed` - 任务失败通知

## 与CLI版本的关系

Web版和CLI版完全**共享**后端核心功能：

- ✅ **配置文件共用**: 使用相同的 `.env` 和 `config.py`
- ✅ **核心模块复用**: 直接调用 `core/` 下的所有模块
- ✅ **输出格式统一**: 生成相同的项目结构和文件格式
- ✅ **项目互通**: Web版创建的项目可以用CLI版继续处理，反之亦然

## 开发说明

### 前端开发
- 基于 Vue3 Composition API
- 使用 Element Plus UI组件库
- Vite 构建工具，支持热更新
- Pinia 状态管理
- Vue Router 路由管理

### 后端开发
- Flask 轻量级Web框架
- Flask-CORS 处理跨域
- Flask-SocketIO 实时通信
- 多线程异步任务处理
- 完整的错误处理和日志记录

### 扩展建议
1. **用户系统**: 可以添加登录注册功能
2. **项目分享**: 支持项目链接分享
3. **模板系统**: 预设不同类型的视频模板
4. **批量处理**: 支持一次上传多个文件
5. **云存储**: 集成云存储服务

## 注意事项

1. **API密钥**: 确保在 `.env` 文件中配置了必要的API密钥
2. **文件大小**: 默认限制上传文件大小为50MB
3. **端口占用**: 确保5000和3000端口未被占用
4. **网络连接**: 某些API服务需要稳定的网络连接
5. **资源消耗**: 视频制作任务会消耗较多CPU和内存资源

---

如需帮助，请查看项目根目录的 README.md 或提交 Issue。