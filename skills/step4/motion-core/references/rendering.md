# 确定性浏览器渲染
ready 等待所有资源。renderAt(t) 直接决定可见状态，不依赖上次调用，反向 seek 必须一致。
浏览器加载失败、外部资源、尺寸不符或采样帧不一致会阻止导出。
python render.py check --snapshots 保存五个采样点；截图只覆盖采样点，需额外验证转场前后。
导出按 frameIndex / fps 逐帧截图，FFmpeg 编码静音 MP4，配音由后续合成步骤处理。
check 不做自动 WCAG 证明、WebGL 内容布局分析或内容事实检查，必须人工读截图。

由 agent 调用 capabilities、preview、render 并检查报告和截图，修复后重跑。最终 video.mp4 只在验证成功后替换；会话结束不会再导出。
视频 seek 使用 await window.clipTools.seekVideo(video,t)，等待解码完成。

反向 seek 的截图比较允许极少量 GPU 边缘像素的小幅栅格化差异；报告会标注容差，明显内容变化仍然报错。
