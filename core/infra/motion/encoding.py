"""Hardware-first encoding shared by the desktop's editing render stages."""
from functools import lru_cache
import os
import shutil
import subprocess
import sys


def ffmpeg_path():
    return os.environ.get('AIGC_FFMPEG_PATH') or shutil.which('ffmpeg') or 'ffmpeg'


def candidates(codec, platform):
    prefix = 'hevc' if codec == 'hevc' else 'h264'
    backends = ('videotoolbox',) if platform == 'darwin' else ('nvenc', 'qsv', 'amf', 'vaapi') if platform.startswith('linux') else ('nvenc', 'qsv', 'amf')
    return [f'{prefix}_{backend}' for backend in backends]


def encoder_args(encoder, width, height):
    if encoder in {'libx264', 'libx265'}:
        return ['-c:v', encoder, '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p']
    # CRF/preset options are not portable between encoder backends. Scale the
    # target bitrate with output pixels and preserve even-sized YUV420 video.
    factor = .12 if encoder.startswith('hevc') else .2
    bitrate = str(max(2_000_000, round(width * height * 30 * factor)))
    args = ['-c:v', encoder, '-b:v', bitrate, '-pix_fmt', 'yuv420p']
    if encoder.endswith('_videotoolbox'):
        args += ['-allow_sw', '0']
    if encoder.startswith('hevc'):
        args += ['-tag:v', 'hvc1']
    return args


def select_encoder(executable, codec, width, height, platform):
    return _select_encoder(executable,codec,width,height,platform,os.environ.get('AIGC_VIDEO_ENCODER','auto'))


@lru_cache(maxsize=32)
def _select_encoder(executable, codec, width, height, platform, requested):
    failures = []
    software='libx265' if codec=='hevc' else 'libx264'
    if requested=='software':
        print('Software encoding explicitly requested: '+software,flush=True)
        return software
    if requested not in {'auto',*candidates(codec,platform),software}:
        raise ValueError('Unsupported encoder for this codec/platform: '+requested)
    for encoder in (candidates(codec, platform) if requested=="auto" else [requested]):
        # A compiled encoder is not proof of usable hardware. Try one frame at
        # the real dimensions to catch driver, device and size limitations.
        try:
            result = subprocess.run([
                executable, '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                f'color=s={width}x{height}:r=30', '-frames:v', '1', '-an',
                *encoder_args(encoder, width, height), '-f', 'null', '-',
            ], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                print(f'使用硬件视频编码：{encoder}', flush=True)
                return encoder
            reason = result.stderr.strip().splitlines()
            failures.append(f'{encoder}: {reason[-1] if reason else "测试失败"}')
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(f'{encoder}: {error}')
    software = 'libx265' if codec == 'hevc' else 'libx264'
    print(f'硬件编码不可用，回退 {software}；原因：' + '; '.join(failures), flush=True)
    return software


select_encoder.cache_clear = _select_encoder.cache_clear


def encode(run_ffmpeg, *inputs, output, width, height, codec='h264', extra=()):
    encoder = select_encoder(ffmpeg_path(), codec, width, height, sys.platform)
    try:
        result=run_ffmpeg(*inputs, *encoder_args(encoder, width, height), *extra, output)
        if result is not None:result.aigc_encoder=encoder
        return result
    except subprocess.CalledProcessError as error:
        if encoder in {'libx264', 'libx265'}:
            raise
        software = 'libx265' if codec == 'hevc' else 'libx264'
        print(f'{encoder} 实际编码失败（退出码 {error.returncode}），回退 {software}。', flush=True)
        result=run_ffmpeg(*inputs, *encoder_args(software, width, height), *extra, output)
        if result is not None:result.aigc_encoder=software
        return result
