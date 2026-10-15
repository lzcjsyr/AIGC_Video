"""HTML → exact timestamp screenshots → verified, silent MP4 clips."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

from .runtime import browser_path, modules_dir, parse_size, subprocess_env, prepare_assets, localize_legacy
from .encoding import select_encoder, encoder_args
from .artifacts import signature, current, stamp


def _tool(name):
    return os.environ.get('AIGC_' + name.upper() + '_PATH') or shutil.which(name, path=subprocess_env()['PATH']) or name


def verify_sources(payload):
    guard=payload.get('sourceGuard')
    if not guard:return
    script=json.loads(Path(guard['script']).read_text(encoding='utf-8'))
    segment=next((s for s in script.get('segments',[]) if s.get('index')==payload.get('segmentIndex')),None)
    if not segment or segment.get('content')!=payload.get('content') or stamp(guard['audio'])!=guard['audioStamp']:
        raise ValueError('Narration or recording changed. Refresh this motion session before rendering.')


def capture(work, payload, *, mode='check', fps=30, destination=None, times=None, caption_zone=True, entry='index.html'):
    work = Path(work).resolve()
    verify_sources(payload)
    source=(work/entry).resolve()
    if not source.is_relative_to(work) or not source.is_file():raise ValueError('HTML entry must exist inside its working folder.')
    entry=source.relative_to(work).as_posix()
    width, height = parse_size(f"{payload['width']}x{payload['height']}")
    duration = float(payload['durationSeconds'])
    if not math.isfinite(duration) or duration <= 0 or not 1 <= int(fps) <= 120:
        raise ValueError('Duration must be positive and fps between 1 and 120.')
    destination = Path(destination or work / 'snapshots').resolve()
    report = work / ('capture-report.json' if mode == 'render' else 'check-report.json')
    last_frame = (math.ceil(duration * fps - 1e-9) - 1) / fps
    samples = times if times is not None else [i * last_frame / 4 for i in range(5)]
    if any(not math.isfinite(t) or t < 0 or t >= duration for t in samples):
        raise ValueError('Snapshot timestamps must be inside the clip duration.')
    spec = dict(work=str(work), payload=payload, width=width, height=height, duration=duration, fps=int(fps),
                browser=browser_path(), modules=str(modules_dir()), mode=mode, times=samples,
                destination=str(destination), report=str(report), captionZone=caption_zone,entry=entry,
                browserMode=os.environ.get('AIGC_BROWSER_MODE','auto'))
    result = subprocess.run([shutil.which('node', path=subprocess_env()['PATH']) or 'node',
                             str(Path(__file__).with_name('capture.cjs'))],
                            input=json.dumps(spec), text=True, capture_output=True, env=subprocess_env(),
                            timeout=max(90, duration * 90))
    if result.stdout:
        print(result.stdout.strip(), flush=True)
    if result.returncode:
        raise RuntimeError('Browser capture failed: ' + result.stderr.strip())
    return json.loads(report.read_text())


def render_clip(work, payload, output, *, fps=30, caption_zone=True, entry='index.html', strict_duration=False, force=False):
    """Keep the prior video until browser capture, encoding and FFprobe all succeed."""
    work, output = Path(work).resolve(), Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height = parse_size(f"{payload['width']}x{payload['height']}")
    duration = float(payload['durationSeconds'])
    verify_sources(payload)
    prepare_assets(work)
    localize_legacy(work,entry)
    def reusable(path):
        if not current(work,payload,path,entry=entry,fps=fps):return False
        report=json.loads(Path(path).with_suffix('.render.json').read_text())
        mode=os.environ.get('AIGC_BROWSER_MODE','auto');encoder=os.environ.get('AIGC_VIDEO_ENCODER','auto')
        if mode!='auto' and report.get('browserMode')!=mode:return False
        if encoder!='auto' and report.get('encoder')!=('libx264' if encoder=='software' else encoder):return False
        if strict_duration and abs(report['authoredDuration']-duration)>.5/fps:return False
        return True
    if not force and reusable(output):
        print(f'Reusing verified render: {output}',flush=True)
        return str(output)
    if not force:
        for cached in [work/'video.mp4',work/'previews/preview.mp4']:
            if cached==output or not reusable(cached):continue
            report=json.loads(cached.with_suffix('.render.json').read_text())
            if strict_duration and abs(report['authoredDuration']-duration)>.5/fps:continue
            temporary=output.with_suffix('.tmp.mp4');shutil.copy2(cached,temporary);temporary.replace(output)
            report.update(output=str(output),output_stamp=stamp(output))
            output.with_suffix('.render.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            (work/'render-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(f'Reusing verified preview: {cached}',flush=True)
            return str(output)
    revision=signature(work,payload,entry=entry,fps=fps,output=output)
    # Validate actual browser behavior, including backward seeking, before encoding.
    checked=capture(work, payload, fps=fps, caption_zone=caption_zone,entry=entry)
    if strict_duration and abs(checked['authoredDuration']-duration)>.5/fps:
        raise ValueError('Custom HTML duration does not match its scene.')
    with tempfile.TemporaryDirectory(prefix='motion-frames-', dir=output.parent) as temporary:
        folder = Path(temporary)
        report = capture(work, payload, mode='render', fps=fps, destination=folder, caption_zone=caption_zone,entry=entry)
        candidate = folder / 'candidate.mp4'
        ffmpeg = _tool('ffmpeg')
        encoder = select_encoder(ffmpeg, 'h264', width, height, sys.platform)
        inputs = [ffmpeg, '-nostdin', '-y', '-v', 'error', '-framerate', str(fps), '-i',
                  str(folder / 'frame-%06d.png'), '-frames:v', str(report['frames']), '-an']
        def encode(selected):
            return subprocess.run([*inputs, *encoder_args(selected, width, height), '-movflags', '+faststart', str(candidate)],
                                  check=True, capture_output=True, text=True, timeout=max(120, duration * 30))
        try:
            encode(encoder)
        except subprocess.CalledProcessError as error:
            if encoder == 'libx264':
                raise RuntimeError('Video encoding failed: ' + error.stderr) from error
            print(f'{encoder} failed; falling back to libx264: {error.stderr}', flush=True)
            encoder = 'libx264'
            encode(encoder)
        probe = subprocess.run([_tool('ffprobe'), '-v', 'error', '-count_frames', '-show_streams', '-show_format',
                                '-of', 'json', str(candidate)], check=True, capture_output=True, text=True, timeout=30)
        metadata = json.loads(probe.stdout)
        videos = [s for s in metadata['streams'] if s['codec_type'] == 'video']
        if len(videos) != 1:
            raise RuntimeError('Export must contain exactly one video stream.')
        video = videos[0]
        if ((video['width'], video['height']) != (width, height) or int(video['nb_read_frames']) != report['frames']
                or abs(float(metadata['format']['duration']) - report['frames'] / fps) > 1 / fps + .001
                or video['codec_name'] != 'h264'
                or abs(float(video['avg_frame_rate'].split('/')[0]) / float(video['avg_frame_rate'].split('/')[1]) - fps) > .001
                or any(s['codec_type'] == 'audio' for s in metadata['streams'])):
            raise RuntimeError('Export failed dimensions, frame count, duration or silent-video validation.')
        if revision!=signature(work,payload,entry=entry,fps=fps,output=output):
            raise RuntimeError('Composition sources changed during rendering; render again.')
        verify_sources(payload)
        candidate.replace(output)
        report.update(encoder=encoder, output=str(output), verified=True,input_signature=revision,output_stamp=stamp(output))
        (work / 'render-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        sidecar=output.with_suffix('.render.json');temporary=sidecar.with_suffix('.tmp')
        temporary.write_text(json.dumps(report,indent=2),encoding='utf-8');temporary.replace(sidecar)
        (work/'render-status.json').write_text(json.dumps({'phase':'verified','completed':report['frames'],'total':report['frames']}),encoding='utf-8')
    return str(output)


def main(work=None):
    parser = argparse.ArgumentParser(description='Check, snapshot or export a local HTML motion clip.')
    parser.add_argument('command', choices=['capabilities','check', 'snapshot', 'preview', 'render'])
    parser.add_argument('--snapshots', action='store_true')
    parser.add_argument('--at', help='Comma-separated seconds')
    parser.add_argument('--frames', type=int, default=5)
    parser.add_argument('--fps', type=int)
    parser.add_argument('--output', default='video.mp4')
    parser.add_argument('--browser-mode',choices=['auto','hardware','software'],default='auto')
    parser.add_argument('--encoder',choices=['auto','software'],default='auto')
    parser.add_argument('--force',action='store_true')
    args = parser.parse_args()
    work = Path(work or Path.cwd())
    payload = json.loads((work / 'studio-payload.json').read_text(encoding='utf-8'))
    args.fps=int(payload.get('fps',30)) if args.fps is None else args.fps
    os.environ['AIGC_BROWSER_MODE']=args.browser_mode;os.environ['AIGC_VIDEO_ENCODER']=args.encoder
    if args.command=='capabilities':
        from .capabilities import inspect_machine
        print(json.dumps(inspect_machine(work,payload,fps=args.fps),indent=2));return
    if args.command in {'preview','render'}:
        output=work/('previews/preview.mp4' if args.command=='preview' and args.output=='video.mp4' else args.output)
        render_clip(work, payload, output, fps=args.fps,force=args.force)
    else:
        if args.frames < 1:
            parser.error('--frames must be positive')
        if args.fps < 1:
            parser.error('--fps must be positive')
        last_frame = max(0, math.ceil(float(payload['durationSeconds']) * args.fps - 1e-9) - 1) / args.fps
        times = list(map(float, args.at.split(','))) if args.at else [
            i * last_frame / max(1, args.frames - 1) for i in range(args.frames)]
        print(json.dumps(capture(work, payload, mode=args.command, fps=args.fps, times=times), indent=2))
