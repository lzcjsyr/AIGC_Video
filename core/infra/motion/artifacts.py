"""Tie rendered artifacts to the exact input revision; ignore generated previews."""
import hashlib
import json
from pathlib import Path

GENERATED = {'snapshots', 'previews', 'build', 'vendor', '__pycache__', 'alignment'}

def stamp(path):
    path = Path(path)
    return f'{path.stat().st_size}:{path.stat().st_mtime_ns}' if path.is_file() else None

def signature(work, payload, *, entry='index.html', fps=30, output=None):
    work=Path(work).resolve()
    output=Path(output).resolve() if output else work/'video.mp4'
    sources=[]
    for file in sorted(work.rglob('*')):
        relative=file.relative_to(work)
        if any(p in GENERATED or p.startswith('.') or p.startswith('motion-frames-') for p in relative.parts) or not file.is_file():continue
        if file.resolve()==output or file.suffix in {'.log','.py','.jsonl'} or file.name.endswith(('-report.json','.render.json','.legacy.html','.task.json')):continue
        if file.name in {'video.mp4','preview.mp4','capabilities.json','render-status.json','poster.jpg'}:continue
        sources.append((relative.as_posix(),stamp(file)))
    runtime=[stamp(Path(__file__).with_name(name)) for name in ('renderer.py','capture.cjs','browser.cjs')]
    return hashlib.sha256(json.dumps([payload,entry,fps,sources,runtime],sort_keys=True).encode()).hexdigest()

def current(work, payload, output, *, entry='index.html', fps=30):
    output=Path(output)
    try:
        report=json.loads(output.with_suffix('.render.json').read_text())
        return bool(report.get('verified') and report.get('output_stamp')==stamp(output)
            and report.get('input_signature')==signature(work,payload,entry=entry,fps=fps,output=output))
    except (OSError,ValueError,TypeError):return False
