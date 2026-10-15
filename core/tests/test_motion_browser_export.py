"""Exercise real browser capture, GPU drawing, encoding and failure preservation."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from core.infra.motion.runtime import prepare
from core.infra.motion.renderer import capture, render_clip

pytestmark = pytest.mark.skipif(not os.environ.get('AIGC_MOTION_MODULES'), reason='Requires staged browser runtime')

HTML = '''<!doctype html><html><head><style>
html,body{margin:0;overflow:hidden}#segment-root{width:100vw;height:100vh;background:#121c34}
#content-wrapper{position:absolute;inset:0 0 20% 0;color:white;font:24px sans-serif;padding:12px;box-sizing:border-box}
canvas{position:absolute;inset:0;width:100%;height:100%}</style>
<script type="importmap">{"imports":{"three":"./vendor/three/build/three.module.js"}}</script></head>
<body><div id="segment-root"><canvas id="scene"></canvas><div id="content-wrapper">系统与关系</div></div>
<script type="module">import * as THREE from 'three'; const p=window.clipPayload;
const renderer=new THREE.WebGLRenderer({canvas:document.getElementById('scene'),antialias:true});
renderer.setSize(p.width,p.height,false);renderer.setPixelRatio(1);const scene=new THREE.Scene();
scene.background=new THREE.Color('#121c34');const camera=new THREE.PerspectiveCamera(40,p.width/p.height,.1,100);
camera.position.z=5; const mesh=new THREE.Mesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshNormalMaterial());scene.add(mesh);
window.clip={...p,ready:Promise.resolve(),renderAt(t){mesh.rotation.x=t;mesh.rotation.y=t*2;renderer.render(scene,camera)}};
</script></body></html>'''


@pytest.fixture
def clip(tmp_path, monkeypatch):
    # Successful exports must not depend on the framework CLI being available.
    monkeypatch.setenv('AIGC_HYPERFRAMES_CLI', '/missing/framework/cli.js')
    work = tmp_path / '中文 clip with spaces'
    payload = dict(width=320, height=180, durationSeconds=.43)
    prepare(work, payload)
    (work / 'index.html').write_text(HTML, encoding='utf-8')
    return work, payload


def test_three_export_exact_frames_silent_video_and_backward_seek(clip):
    work, payload = clip
    output = Path(render_clip(work, payload, work / 'video.mp4', fps=10))
    report = json.loads((work / 'render-report.json').read_text())
    assert report['verified'] and report['frames'] == 5
    probe = json.loads(subprocess.check_output([os.environ['AIGC_FFPROBE_PATH'], '-v', 'error',
        '-show_streams', '-show_format', '-of', 'json', str(output)]))
    assert len(probe['streams']) == 1
    assert probe['streams'][0]['codec_type'] == 'video'
    assert (probe['streams'][0]['width'], probe['streams'][0]['height']) == (320, 180)
    assert abs(float(probe['format']['duration']) - .5) < .01
    check = json.loads((work / 'check-report.json').read_text())
    assert check['success'] and check['frames'] == 5


def test_external_resource_failure_preserves_existing_video(clip):
    work, payload = clip
    output = work / 'video.mp4'; output.write_bytes(b'previous approved video')
    html = work / 'index.html'
    html.write_text(HTML.replace('<head>', '<head><script src="https://invalid.example/animation.js"></script>'))
    with pytest.raises(RuntimeError, match='External resource blocked'):
        render_clip(work, payload, output, fps=10)
    assert output.read_bytes() == b'previous approved video'


def test_nonrepeatable_animation_is_rejected(clip):
    work, payload = clip
    html = work / 'index.html'
    html.write_text(HTML.replace('window.clip={', 'let calls=0;window.clip={').replace('mesh.rotation.y=t*2', 'mesh.rotation.y=++calls*.3'))
    with pytest.raises(RuntimeError, match='Non-repeatable frame'):
        capture(work, payload, fps=10)


def test_caption_zone_overlap_is_rejected(clip):
    work, payload = clip
    (work / 'index.html').write_text(HTML.replace('inset:0 0 20% 0', 'inset:0'))
    with pytest.raises(RuntimeError, match='caption-safe'):
        capture(work, payload, fps=10)


def test_saved_legacy_gsap_clip_exports_without_framework(clip):
    work, payload = clip
    (work / 'index.html').write_text('''<!doctype html><html><head><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>html,body{margin:0;overflow:hidden}#content-wrapper{position:absolute;top:0;width:100%;height:80%;}</style></head>
    <body><div data-composition-id="segment" data-width="320" data-height="180" data-duration=".43">
    <div id="content-wrapper"><div id="box" style="width:40px;height:40px;background:blue"></div></div></div>
    <script>const tl=gsap.timeline({paused:true});tl.to('#box',{x:100,duration:.43});window.__timelines.segment=tl;</script></body></html>''')
    render_clip(work, payload, work / 'video.mp4', fps=10)
    assert (work / 'index.legacy.html').exists()
    assert 'https://cdn' not in (work / 'index.html').read_text()


def test_opening_quote_real_browser_export(tmp_path, monkeypatch):
    from core.config import config
    from core.infra.motion.opening_renderer import render_opening_video
    monkeypatch.setattr(config, 'OPENING_MOTION_DURATION_SECONDS', .43)
    monkeypatch.setattr(config, 'OPENING_MOTION_FPS', 10)
    monkeypatch.setenv('AIGC_HYPERFRAMES_CLI', '/missing/framework/cli.js')
    output = render_opening_video(image_size='1280x720', output_dir=str(tmp_path),
        script_data={'source_name':'系统思维','golden_quotes':['看见系统，理解关系。']})
    assert output and Path(output).stat().st_size > 1000


def test_embedded_video_seek_repeats_the_correct_decoded_frame(clip):
    from PIL import Image
    work,payload=clip
    payload.update(width=160,height=90,durationSeconds=1)
    subprocess.run([os.environ['AIGC_FFMPEG_PATH'],'-y','-v','error','-f','lavfi','-i','color=red:s=160x90:r=10:d=0.5',
        '-f','lavfi','-i','color=blue:s=160x90:r=10:d=0.5','-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0',
        '-c:v','libx264','-pix_fmt','yuv420p',str(work/'movie.mp4')],check=True)
    (work/'index.html').write_text('''<!doctype html><style>html,body{margin:0;overflow:hidden}video{width:160px;height:90px}</style>
    <div id="segment-root"><video id="movie" muted preload="auto" src="movie.mp4"></video></div>
    <script>const p=window.clipPayload;window.clip={...p,ready:Promise.resolve(),async renderAt(t){await window.clipTools.seekVideo(document.getElementById('movie'),t)}};</script>''')
    capture(work,payload,mode='snapshot',fps=10,times=[.1,.7,.1],caption_zone=False)
    colors=[Image.open(work/f'snapshots/frame-{i:06}.png').convert('RGB').getpixel((80,45)) for i in range(3)]
    assert colors[0][0]>200 and colors[0][2]<40
    assert colors[1][2]>200 and colors[1][0]<40
    assert colors[0]==colors[2]


def test_final_render_reuses_verified_preview_and_rejects_changed_assets(clip,monkeypatch):
    from core.infra.motion import renderer
    from core.infra.motion.artifacts import current
    work,payload=clip
    preview=work/'previews/preview.mp4'
    render_clip(work,payload,preview,fps=10)
    # A new agent brief is metadata, not a changed scene.
    (work/'_agent_session.task.json').write_text('{"stage":4}')
    with monkeypatch.context() as patch:
        patch.setattr(renderer,'capture',lambda *a,**k:pytest.fail('Verified preview should be reused'))
        render_clip(work,payload,work/'video.mp4',fps=10)
    assert (work/'video.mp4').read_bytes()==preview.read_bytes()
    assert current(work,payload,work/'video.mp4',fps=10)
    (work/'scene-data.json').write_text('{"changed":true}')
    assert not current(work,payload,work/'video.mp4',fps=10)


def test_capability_report_tests_actual_browser_and_encoders(clip):
    from core.infra.motion.capabilities import inspect_machine
    work,payload=clip
    report=inspect_machine(work,payload,fps=10)
    assert report['verified'] and report['browser']['screenshotVerified']
    assert report['browser']['mode'] in {'hardware','software'}
    assert report['encoders']['h264'] and report['encoders']['hevc']
