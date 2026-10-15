# Three.js
import map 使用本地 vendor/three/build/three.module.js 和 vendor/three/examples/jsm/。
renderer.setSize(payload.width, payload.height, false); renderer.setPixelRatio(1)。
初始化创建 scene、camera 和 renderer；加载纹理、GLTF 和 shader 的工作纳入 clip.ready Promise。
renderAt(t) 显式设置所有变换、透明度、可见性和 camera，再调用 mixer.setTime(t) 和 renderer.render。
不用 renderer.setAnimationLoop、真实时钟、帧增量、阻尼控件和历史帧特效。
文本建议使用 HTML/SVG 叠加；WebGL 内的字幕避让要通过截图人工核实。
