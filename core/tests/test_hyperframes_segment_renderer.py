import json
import subprocess
import wave
from pathlib import Path

from core.infra.project_paths import ProjectPaths


def _write_wav(path: Path, *, seconds: float) -> None:
    frame_rate = 8000
    frame_count = int(frame_rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(frame_rate)
        handle.writeframes(b"\x00\x00" * frame_count)


def _write_project(project_dir: Path) -> ProjectPaths:
    paths = ProjectPaths(str(project_dir))
    paths.ensure_dirs_exist()
    Path(paths.script_json()).write_text(
        json.dumps(
            {
                "actual_segments": 1,
                "segments": [{"index": 1, "content": "收入同比增长30%，利润承压。", "title": "增长与压力"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_wav(Path(paths.voice) / "voice_1.wav", seconds=0.75)
    return paths


def test_step4_motion_skill_loader_uses_project_resources():
    from core.infra.motion.skill_loader import default_step4_motion_skill_dir, build_step4_motion_skill_path_context, step4_motion_skill_dirs
    context = build_step4_motion_skill_path_context()
    assert "counter_burst:" in context and "entry_path:" in context
    assert "hyperframes" not in context.lower()
    assert default_step4_motion_skill_dir().name == "motion-core"
    assert [p.name for p in step4_motion_skill_dirs()] == ["motion-core", "motion-animation", "motion-creative"]


def render_options(project, paths):
    return dict(project_output_dir=str(project), script_data=json.loads(Path(paths.script_json()).read_text()),
        image_size="1280x720",output_dir=paths.images,target_segments=[1],description_data=None,
        style_preset="data_driven",max_turns=7,render_fps=60,concurrency=1,
        session_log_path=str(Path(paths.text)/"session.jsonl"),repo_root=str(project.parent))


def test_segment_renderer_uses_audio_duration_and_absolute_output(monkeypatch, tmp_path):
    from core.infra.motion import segment_renderer
    monkeypatch.chdir(tmp_path)
    project=Path("project");paths=_write_project(project);agents=[];renders=[]
    def agent(**kwargs):
        agents.append(kwargs);work=Path(kwargs['work_dir']);work.mkdir(parents=True,exist_ok=True)
        (work/'index.html').write_text('<html></html>')
    def render(work,payload,output,**kwargs):
        renders.append((work,payload,output,kwargs));assert Path(output).is_absolute()
        Path(output).write_bytes(b'video')
    monkeypatch.setattr(segment_renderer,'run_step4_motion_agent',agent)
    monkeypatch.setattr(segment_renderer,'render_clip',render)
    result=segment_renderer.render_motion_segments_with_agent(**render_options(project,paths))
    assert result['processed_segments']==[1] and not result['failed_segments']
    assert agents[0]['duration_seconds']==.75
    assert renders[0][1]['durationSeconds']==.75
    assert renders[0][3]['fps']==60
    assert Path(renders[0][0]).parts[-2:]==('motion','segment_1')
    assert Path(result['image_paths'][0]).is_file()


def test_segment_renderer_preserves_prior_video_and_logs_failure(monkeypatch,tmp_path):
    from core.infra.motion import segment_renderer
    project=tmp_path/'project';paths=_write_project(project)
    output=Path(paths.images)/'segment_1.mp4';output.write_bytes(b'previous')
    monkeypatch.setattr(segment_renderer,'run_step4_motion_agent',lambda **kwargs:None)
    def fail(*args,**kwargs):raise RuntimeError('capture failed')
    monkeypatch.setattr(segment_renderer,'render_clip',fail)
    result=segment_renderer.render_motion_segments_with_agent(**render_options(project,paths))
    assert result['failed_segments']==[1]
    assert output.read_bytes()==b'previous'
    assert 'capture failed' in (Path(paths.images)/'motion/segment_1/render.log').read_text()


def test_segment_renderer_skips_missing_audio(monkeypatch,tmp_path):
    from core.infra.motion import segment_renderer
    project=tmp_path/'project';paths=_write_project(project)
    (Path(paths.voice)/'voice_1.wav').unlink()
    def fail(**kwargs):raise AssertionError('agent should not run')
    monkeypatch.setattr(segment_renderer,'run_step4_motion_agent',fail)
    result=segment_renderer.render_motion_segments_with_agent(**render_options(project,paths))
    assert result['missing_audio_segments']==[1]
