from core.domain.summarizer import process_raw_to_script
import pytest


def contents(text, target=50, mode="punctuation"):
    return [s["content"] for s in process_raw_to_script({"content": text}, target, mode)["segments"]]


@pytest.mark.parametrize("stop", [".", "。", "．", "?", "？", "!", "！", ";", "；"])
def test_punctuation_splits_at_each_english_and_chinese_terminal(stop):
    assert contents(f"First{stop}Second{stop}Tail") == [f"First{stop}", f"Second{stop}", "Tail"]


@pytest.mark.parametrize("target", [1, 2, 50, 200])
def test_punctuation_ignores_target_without_merging_short_or_splitting_long_sentences(target):
    long = "很长的句子，包含逗号但不在逗号切分" * 30 + "。"
    assert contents("好。是的！为什么？" + long, target) == ["好。", "是的！", "为什么？", long]


def test_punctuation_keeps_decimal_numbers_closing_quotes_and_punctuation_runs():
    text = '价格是3.14元。他问：“Ready?!” Then said: "Yes."（真的？！）结束；'
    assert contents(text) == ['价格是3.14元。', '他问：“Ready?!”', 'Then said: "Yes."', '（真的？！）', '结束；']


def test_punctuation_does_not_invent_newline_boundaries_or_punctuation():
    assert contents("第一行未结束\n第二行才结束。\n最后一段") == ["第一行未结束\n第二行才结束。", "最后一段"]
    assert contents(" , \n ") == [","]


def test_legacy_auto_now_uses_punctuation_and_keeps_motion_markers():
    raw = {"content": "一。【motion】二？三；"}
    script = process_raw_to_script(raw, 1, "auto")
    assert [s["content"] for s in script["segments"]] == ["一。", "二？", "三；"]
    assert [s["visualizer"] for s in script["segments"]] == ["hf", "image", "image"]
    assert script["target_segments"] == script["actual_segments"] == 3


def test_manual_target_is_ignored():
    assert contents("Line one. Line two?\nLine three!", 1, "manual") == ["Line one. Line two?", "Line three!"]


def test_agent_segments_keep_script_shape_and_visualizer_choices():
    raw_data = {
        "source_name": "原始作品",
        "video_titles": ["测试"],
        "cover_titles": ["测试"],
        "cover_subtitles": [],
        "golden_quotes": [],
        "content": "收入增长了百分之三十，但利润率继续承压。小镇的夜雨落下来，母亲把灯留到很晚。",
    }

    script = process_raw_to_script(
        raw_data,
        num_segments=2,
        split_mode="agent",
        agent_segments=[
            {"content": "收入增长了百分之三十，但利润率继续承压。", "visualizer": "hf"},
            {"content": "小镇的夜雨落下来，母亲把灯留到很晚。", "visualizer": "image"},
        ],
    )

    assert script["actual_segments"] == 2
    assert script["segments"][0]["index"] == 1
    assert script["segments"][0]["visualizer"] == "hf"
    assert script["segments"][1]["visualizer"] == "image"
    assert "length" in script["segments"][0]
    assert "estimated_duration" in script["segments"][0]


def test_agent_segments_reject_legacy_hyper_visualizer():
    raw_data = {
        "video_titles": ["测试"],
        "content": "收入增长了百分之三十，但利润率继续承压。",
    }

    with pytest.raises(ValueError, match="visualizer 不支持: hyper"):
        process_raw_to_script(
            raw_data,
            num_segments=1,
            split_mode="agent",
            agent_segments=[
                {"content": "收入增长了百分之三十，但利润率继续承压。", "visualizer": "hyper"},
            ],
        )


def test_manual_split_hf_marker_sets_visualizer_and_removes_marker():
    raw_data = {
        "video_titles": ["测试"],
        "content": "第一段普通画面。\n第二段调用动态画面。【hf】\n第三段普通画面。",
    }

    script = process_raw_to_script(raw_data, num_segments=3, split_mode="manual")

    assert [segment["content"] for segment in script["segments"]] == [
        "第一段普通画面。",
        "第二段调用动态画面。",
        "第三段普通画面。",
    ]
    assert [segment["visualizer"] for segment in script["segments"]] == ["image", "hf", "image"]


def test_agent_split_keeps_same_script_contract_as_rule_modes():
    raw_data = {
        "source_name": "测试来源",
        "video_titles": ["测试"],
        "cover_titles": ["封面"],
        "cover_subtitles": ["副标题"],
        "golden_quotes": ["金句。"],
        "content": "收入增长很快，但利润率承压。她走进雨夜，把灯留在窗口。",
    }

    auto_script = process_raw_to_script(raw_data, num_segments=2, split_mode="auto")
    agent_script = process_raw_to_script(
        raw_data,
        num_segments=2,
        split_mode="agent",
        agent_segments=[
            {"content": "收入增长很快，但利润率承压。", "visualizer": "hf"},
            {"content": "她走进雨夜，把灯留在窗口。", "visualizer": "image"},
        ],
    )

    assert set(agent_script) == set(auto_script)
    assert set(agent_script["segments"][0]) == set(auto_script["segments"][0])
    assert agent_script["actual_segments"] == len(agent_script["segments"])
    assert [segment["index"] for segment in agent_script["segments"]] == [1, 2]


def test_agent_segments_accept_sentence_ending_before_straight_quote():
    raw_data = {
        "video_titles": ["测试"],
        "content": '他说："你们一定是来叫魂的！"人群越聚越多。',
    }

    script = process_raw_to_script(
        raw_data,
        num_segments=2,
        split_mode="agent",
        agent_segments=[
            {"content": '他说："你们一定是来叫魂的！"', "visualizer": "image"},
            {"content": "人群越聚越多。", "visualizer": "image"},
        ],
    )

    assert script["actual_segments"] == 2


def test_agent_segments_reject_split_inside_sentence():
    raw_data = {
        "video_titles": ["测试"],
        "content": "收入增长了百分之三十，但利润率继续承压。",
    }

    with pytest.raises(ValueError, match="句子内部"):
        process_raw_to_script(
            raw_data,
            num_segments=2,
            split_mode="agent",
            agent_segments=[
                {"content": "收入增长了百分之三十，", "visualizer": "hf"},
                {"content": "但利润率继续承压。", "visualizer": "hf"},
            ],
        )
