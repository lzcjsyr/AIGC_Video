---
name: html-motion-core
description: 制作可逐帧 seek 的 HTML / Three.js 动画片段。
---

读取 window.clipPayload，声明 window.clip 的 width、height、durationSeconds、ready Promise 和 renderAt(seconds)。
GSAP、SVG 和 Three.js 都由显式时间驱动。只用 vendor/ 本地资源，不用真实时钟或外部网络。
执行 python render.py check --snapshots，读截图检查构图、文字和字幕安全区。
技术细节见 references/rendering.md 与 references/three.md。
