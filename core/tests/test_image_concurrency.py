import threading
import time
import json
import os
import subprocess
import sys

import pytest

from core.infra.ai import image_client


@pytest.mark.parametrize("provider,ceiling", [("google", 1), ("google_adc", 1), ("doubao", 5)])
def test_image_requests_respect_provider_ceiling(monkeypatch, tmp_path, provider, ceiling):
    monkeypatch.setattr(image_client.config, "MAX_CONCURRENT_IMAGE_GENERATION", 20)
    monkeypatch.setattr(image_client.config, "SEEDREAM_MAX_CONCURRENT_IMAGE_GENERATION", 20)
    active = peak = 0
    lock = threading.Lock()

    def generate(args):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(.03)
        with lock:
            active -= 1
        return {"success": True, "segment_index": args[0], "image_path": str(tmp_path / f"segment_{args[0]}.png")}

    monkeypatch.setattr(image_client, "_generate_single_image", generate)
    result = image_client.generate_images_for_segments(
        provider, "test-model", {"segments": [{"index": i, "content": "Test"} for i in range(1, 9)]},
        "test-style", "640x360", str(tmp_path), description_data={"summary": "Test summary"},
    )
    assert not result["failed_segments"]
    assert peak == ceiling


def test_lower_concurrency_setting_is_respected(monkeypatch):
    monkeypatch.setattr(image_client.config, "SEEDREAM_MAX_CONCURRENT_IMAGE_GENERATION", 2)
    assert image_client.image_generation_workers("doubao") == 2


@pytest.mark.parametrize("providers,ceiling", [(("google", "google_adc"), 1), (("doubao", "doubao"), 5)])
def test_provider_ceiling_is_shared_across_job_processes(tmp_path, providers, ceiling):
    code = '''
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from core.infra.ai.image_concurrency import provider_slot
def request(_):
    with provider_slot(sys.argv[1]):
        start=time.time();time.sleep(.08);return (start,time.time())
with ThreadPoolExecutor(max_workers=4) as pool: print(json.dumps(list(pool.map(request,range(4)))))
'''
    env = {**os.environ, "AIGC_IMAGE_CONCURRENCY_DIR": str(tmp_path)}
    jobs = [subprocess.Popen([sys.executable, "-c", code, provider], env=env, stdout=subprocess.PIPE, text=True) for provider in providers]
    intervals = []
    for job in jobs:
        output, _ = job.communicate(timeout=30)
        assert job.returncode == 0
        intervals.extend(json.loads(output))
    assert len(intervals) == 8
    peak = max(sum(start <= point < end for start, end in intervals) for point, _ in intervals)
    assert 1 <= peak <= ceiling
