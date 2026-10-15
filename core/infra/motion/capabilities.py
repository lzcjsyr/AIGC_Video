"""Measure local browser and encoder support instead of guessing from machine names."""
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from .runtime import browser_path,modules_dir,subprocess_env
from .encoding import select_encoder

def inspect_machine(work,payload,fps=30):
    from .renderer import _tool
    spec=dict(browser=browser_path(),modules=str(modules_dir()),width=int(payload['width']),height=int(payload['height']),
              browserMode=os.environ.get('AIGC_BROWSER_MODE','auto'))
    result=subprocess.run([shutil.which('node',path=subprocess_env()['PATH']) or 'node',str(Path(__file__).with_suffix('.cjs'))],
        input=json.dumps(spec),capture_output=True,text=True,env=subprocess_env(),timeout=90)
    if result.returncode:raise RuntimeError('Browser capability test failed: '+result.stderr.strip())
    report=dict(os=sys.platform,architecture=platform.machine(),width=spec['width'],height=spec['height'],fps=fps,
                browser=json.loads(result.stdout),encoders={})
    for codec in ('h264','hevc'):
        encoder=select_encoder(_tool('ffmpeg'),codec,spec['width'],spec['height'],sys.platform)
        report['encoders'][codec]=encoder
        # A listed encoder is insufficient: verify actual frame encoding at output size/fps.
        from .encoding import encoder_args
        probe=subprocess.run([_tool('ffmpeg'),'-nostdin','-v','error','-f','lavfi','-i',
            f"color=s={spec['width']}x{spec['height']}:r={fps}",'-frames:v','2','-an',
            *encoder_args(encoder,spec['width'],spec['height']),'-f','null','-'],capture_output=True,text=True,timeout=30)
        if probe.returncode:raise RuntimeError(f'{codec} encoding capability test failed: '+probe.stderr.strip())
    report['verified']=True
    target=Path(work)/'capabilities.json';temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report,indent=2),encoding='utf-8');temporary.replace(target)
    return report
