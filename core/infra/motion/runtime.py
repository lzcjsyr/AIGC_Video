"""Locate the browser runtime without invoking a video framework or npm downloads."""
import os
import shutil
from pathlib import Path


def subprocess_env():
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join([env.get('PATH', ''), '/opt/homebrew/bin', '/usr/local/bin'])
    return env


def parse_size(size):
    width, height = map(int, str(size or '1280x720').lower().replace(' ', '').replace('×', 'x').replace('*', 'x').split('x'))
    if not (2 <= width <= 8192 and 2 <= height <= 8192) or width % 2 or height % 2:
        raise ValueError('Video dimensions must be even integers between 2 and 8192.')
    return width, height


def modules_dir():
    configured = os.environ.get('AIGC_MOTION_MODULES')
    root = Path(configured) if configured else Path(__file__).parent / 'node_modules'
    for name in ('puppeteer-core', 'three', 'gsap'):
        if not (root / name / 'package.json').is_file():
            raise RuntimeError('Motion runtime missing. Run npm ci in core/infra/motion, or reinstall Studio.')
    return root.resolve()


def browser_path():
    configured = os.environ.get('AIGC_BROWSER_PATH')
    candidates = [configured, shutil.which('chrome'), shutil.which('chromium'),
                  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                  str(Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'),
                  str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Google/Chrome/Application/chrome.exe')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise RuntimeError('Chrome is unavailable. Set AIGC_BROWSER_PATH to a Chrome/Chromium executable.')


def prepare_assets(work):
    """Install shared local JS without touching an editing plan's payload."""
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    modules = modules_dir()
    shutil.copytree(modules / 'three/build', work / 'vendor/three/build', dirs_exist_ok=True)
    shutil.copytree(modules / 'three/examples/jsm', work / 'vendor/three/examples/jsm', dirs_exist_ok=True)
    (work / 'vendor').mkdir(exist_ok=True)
    shutil.copy2(modules / 'gsap/dist/gsap.min.js', work / 'vendor/gsap.min.js')


def prepare(work, payload):
    """Install local assets and a project-scoped renderer command."""
    import json
    work = Path(work).resolve()
    prepare_assets(work)
    (work / 'studio-payload.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    engine = Path(__file__).resolve().parents[3]
    (work / 'render.py').write_text(
        'import sys\nfrom pathlib import Path\n'
        f'sys.path.insert(0, {str(engine)!r})\n'
        'from core.infra.motion.renderer import main\n'
        'if __name__ == "__main__": main(Path(__file__).resolve().parent)\n', encoding='utf-8')


def localize_legacy(work, entry='index.html'):
    """Retain saved HTML artwork while replacing known CDN imports with local files."""
    import re
    file = Path(work) / entry
    source = file.read_text(encoding='utf-8')
    if 'window.clip' in source:
        return
    vendor = Path(os.path.relpath(Path(work) / 'vendor', file.parent)).as_posix()
    updated = re.sub(r'https://cdn\.jsdelivr\.net/npm/gsap@[^/]+/dist/gsap\.min\.js', vendor + '/gsap.min.js', source)
    updated = re.sub(r'https://cdn\.jsdelivr\.net/npm/three@[^/]+/(?:\+esm|build/three\.module(?:\.min)?\.js)',
                     vendor + '/three/build/three.module.js', updated)
    updated = re.sub(r'https://cdn\.jsdelivr\.net/npm/three@[^/]+/examples/jsm/', vendor + '/three/examples/jsm/', updated)
    if source != updated:
        backup = file.with_suffix('.legacy.html')
        if not backup.exists():
            shutil.copy2(file, backup)
        file.write_text(updated, encoding='utf-8')
