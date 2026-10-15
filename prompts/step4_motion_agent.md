<!-- STEP4_MOTION_PROMPT_VERSION: 2026-10-15-agent-render-v2 -->
为当前单个旁白段落制作可确定性渲染的 HTML 动画，写入 `{target_index_html_path}`。
只在本段工作目录写 index.html 和辅助素材，不修改其他段落、源码、稿件或配音。

## 内容与设计
从当前 payload.content 提炼 visualKeywords：hero 为 2–8 个中文字符，support 最多 1 个 4–12 字短语；contrast 可选最多 2 个短词。
屏幕可读中文总量不超过 28 字，不照搬完整旁白或连续超过 12 字原文。标题和摘要只提供上下文，不添加新事实。
先规划阅读路径、焦点和动作关系，再编写 HTML。避免只摆文字卡片；根据观点选择对比、因果、数量或空间关系。
每段选择一个主要动作，内容跟随叙述逐步出现，结尾保留阅读时间。可以使用 HTML/CSS/SVG、GSAP、Canvas 或 Three.js；不强制使用 3D。
前台内容放在 #content-wrapper，底部 20% 留给后续字幕。纯背景装饰可以在该区域延伸。
根元素为 #segment-root，宽高覆盖画布，无滚动条。#content-wrapper 位于画布上方 80%，用相对尺寸 padding 和布局。
中文字体使用 "PingFang SC", "Noto Sans SC", sans-serif；只用本机字体或本地文件。字号按 payload.width 等比例设计；确保中文不会裁切且对比清晰。

默认视频在手机中观看：以 2560×1440 为参考，主关键词至少 200px、辅助短语至少 72px、核心数字至少 320px；其他画布按比例缩放。主字至少为辅助字的 1.8 倍。
信息文字透明度至少 0.78；标签至少 0.62；低于 0.4 的透明度只用于装饰。每段至少一个清晰焦点色。
不要留下孤立数字和无关系的信息岛。可选布局：左右对比、数字到结论、因果流程、中心辐射、图表加短判断。

## 浏览器片段契约
index.html 必须读取 `window.clipPayload`，直接打开时可用内嵌的本段 payload 作为默认值。
必须定义 `window.clip = {{ width, height, durationSeconds, ready, renderAt }}`：
- width、height、durationSeconds 来自 payload。改变画布时需要更新布局和 WebGL renderer 尺寸。
- ready 是 Promise；所有模型、纹理、字体和 shader 初始化完成后才 resolve，加载失败必须 reject。
- renderAt(seconds) 必须在任意时间点重建完整画面，包括从后往前 seek；可以返回 Promise，但必须等绘制完成。
- ready 完成后调用 renderAt(0)，让直接打开 HTML 的浏览器也能看到首帧；正式导出时由渲染脚本逐帧设置时间。
- 不能使用真实时间、随机数、setTimeout、自由运行的 requestAnimationFrame 或 autoplay 作为动画依据。
- GSAP 时间线必须 paused，renderAt 调用 tl.totalTime(seconds, false)。所有 tween 都放进这条时间线。
- Three.js 使用本地 import map，renderAt 内设置对象/相机状态，mixer.setTime(seconds)，renderer.render(scene,camera)。像素比固定 1。
- 支持有限循环；不用无限循环和有前帧历史依赖的特效。所有粒子用固定 seed 或固定初始数组。
- 不嵌入配音、音乐或字幕；应用之后统一混音。
- 所有资源必须是本段目录中的本地文件。禁止 CDN、外部网络请求、npm 安装或引用其他项目路径。

本段已提供 vendor/gsap.min.js、vendor/three/build/three.module.js 和 vendor/three/examples/jsm/。
GSAP 引用：`<script src="vendor/gsap.min.js"></script>`。
Three.js import map 将 "three" 映射到 "./vendor/three/build/three.module.js"，"three/addons/" 映射到 "./vendor/three/examples/jsm/"。
不要修改或删除 vendor/、studio-payload.json 或 render.py。

## 验证
写入后在本段目录运行 `python render.py check --snapshots`。
该命令检查浏览器错误、本地资源加载、clip 契约、画布溢出、DOM 字幕避让及采样帧的反向 seek 可重复性，并保存 snapshots/ 与 check-report.json。
它不能判断 Canvas/Three.js 内的文字和对象是否遮挡字幕，也不能自动证明视觉质量；必须读截图检查可读性、对比度、中文裁切、主题和字幕区。
需要指定时间时运行 `python render.py snapshot --at 0.5,1.5`，或 `python render.py snapshot --frames 5`。
失败就修复 HTML 并重跑检查。由你负责预览、检查、修复和最终导出，不要等待用户手动开始渲染。
先运行 `python render.py capabilities` 读取本机 capabilities.json。以实测浏览器 GPU、编码器和回退原因作决定，不要凭机器型号猜测。
运行 `python render.py preview` 生成完整时长预览，读 snapshots/ 并用 FFmpeg 从预览中抽取转场前后帧检查；修复后再次预览。
满意后运行 `python render.py render` 生成本段 video.mp4。未改变的已验证预览会被复用，不重复捕获。
核对 render-report.json 的 verified、帧数、尺寸、时长和实际硬件路径。若更改 HTML 或资源必须重新导出。
工具支持 --browser-mode auto/hardware/software 和 --encoder auto/software。默认优先使用实测可用硬件；失败先读诊断，只有硬件不可用、失败或用户明确要求时选软件，说明原因。
--force 可强制重渲染。不要覆盖其他段落或本段的其他版本。

## 风格
所选风格：{style_preset}
{style_context}

## 可选参考
{skill_path_context}

## 本段输入
```json
{payload_json}
```
