import json
from importlib import import_module

from core.config import VideoGenerationConfig
from core.infra.project_paths import ProjectPaths

run_auto_module = import_module("core.pipeline.run_auto")


def test_run_auto_success_uses_raw_data_for_cover_and_statistics(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    paths = ProjectPaths(str(project_dir))
    paths.ensure_dirs_exist()

    raw_data = {
        "source_name": "source",
        "video_titles": ["title"],
        "cover_titles": ["cover"],
        "cover_subtitles": ["subtitle"],
        "golden_quotes": ["quote"],
        "content": "x" * 1000,
        "total_length": 1000,
    }
    paths.raw_json()
    with open(paths.raw_json(), "w", encoding="utf-8") as handle:
        json.dump(raw_data, handle)

    script_data = {
        "total_length": 250,
        "actual_segments": 5,
        "segments": [{"index": idx, "content": f"segment {idx}"} for idx in range(1, 6)],
    }

    captured = {}

    def fake_step_1(*args, **kwargs):
        captured["step1_args"] = args
        captured["step1_kwargs"] = kwargs
        return {
            "success": True,
            "project_output_dir": str(project_dir),
            "raw": {"total_length": 1000},
        }

    monkeypatch.setattr(run_auto_module, "_run_step_1", fake_step_1)
    def fake_step_1_5(*args, **kwargs):
        captured["step15_args"] = args
        captured["step15_kwargs"] = kwargs
        return {
            "success": True,
            "script_data": script_data,
            "script_path": paths.script_json(),
        }

    monkeypatch.setattr(run_auto_module, "_run_step_1_5", fake_step_1_5)

    def fake_step_2(*_args, **_kwargs):
        summary_path = paths.mini_summary_json()
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump({"summary": "summary", "total_length": 7}, handle)
        return {"success": True, "mini_summary_path": summary_path}

    monkeypatch.setattr(run_auto_module, "_run_step_2", fake_step_2)
    monkeypatch.setattr(
        run_auto_module,
        "_run_step_3",
        lambda *_args, **_kwargs: {
            "success": True,
            "audio_paths": [f"voice_{idx}.wav" for idx in range(1, 6)],
        },
    )
    def fake_step_4(*args, **kwargs):
        captured["step4_args"] = args
        captured["step4_kwargs"] = kwargs
        return {
            "success": True,
            "image_paths": [f"image_{idx}.png" for idx in range(1, 6)],
        }

    monkeypatch.setattr(run_auto_module, "_run_step_4", fake_step_4)
    monkeypatch.setattr(
        run_auto_module,
        "_run_step_5",
        lambda *_args, **_kwargs: {"success": True, "final_video": paths.final_video()},
    )

    def fake_cover_generation(*args):
        captured["raw_data"] = args[-1]
        return {"success": True, "cover_paths": ["cover.png"]}

    monkeypatch.setattr(run_auto_module, "_run_cover_generation", fake_cover_generation)

    config = VideoGenerationConfig(
        input_file="input.pdf",
        output_dir=str(tmp_path),
        num_segments=5,
        llm_server_step2="siliconflow",
        llm_base_url_step2="https://example.test/v1",
        llm_server_step4="siliconflow",
        llm_base_url_step4="https://example.test/v1",
        image_server="google",
        image_model="gemini-3.1-flash-image",
        image_size="1280x720",
        image_prompt_template="pure_images",
        visual_mode="hyperframes_agent",
        hyperframes_style_preset="light_corporate",
        hyperframes_max_turns=9,
        hyperframes_render_fps=60,
        hyperframes_concurrency=2,
        step1_5_split_mode="agent",
        llm_server_step1_5="kimi",
        llm_model_step1_5="kimi-k2.6",
        cover_image_server="google",
        cover_image_model="gemini-3.1-flash-image",
        cover_image_size="1280x720",
        extra_requirements="突出商业启示",
    )

    result = run_auto_module.run_auto(config)

    assert result["success"] is True
    assert result["statistics"]["original_length"] == 1000
    assert result["statistics"]["compression_ratio"] == "75.0%"
    assert result["cover_images"] == ["cover.png"]
    assert captured["raw_data"]["content"] == "x" * 1000
    assert captured["step1_kwargs"]["extra_requirements"] == "突出商业启示"
    assert captured["step15_kwargs"]["split_mode"] == "agent"
    assert captured["step15_kwargs"]["llm_server_step1_5"] == "kimi"
    assert captured["step15_kwargs"]["llm_model_step1_5"] == "kimi-k2.6"
    assert captured["step4_kwargs"]["visual_mode"] == "hyperframes_agent"
    assert captured["step4_kwargs"]["hyperframes_style_preset"] == "light_corporate"
    assert captured["step4_kwargs"]["hyperframes_max_turns"] == 9
    assert captured["step4_kwargs"]["hyperframes_render_fps"] == 60
    assert captured["step4_kwargs"]["hyperframes_concurrency"] == 2
    assert captured["step4_kwargs"]["image_prompt_template"] == "pure_images"
