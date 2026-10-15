"""An agent's brief carries boundaries and input revisions, not source bodies."""
import json
from core.infra.ai.task_context import write_task_context


def test_task_manifest_is_small_source_bound_and_contains_no_input_bodies_or_environment(tmp_path, monkeypatch):
    source = tmp_path/'source.txt'
    source.write_text('PRIVATE_SOURCE_BODY' * 10000)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'PRIVATE_PROVIDER_KEY')
    target = tmp_path/'session/task.json'
    output = tmp_path/'text/raw.json'
    prompt = write_task_context(target, stage='2', objective='Segment only', cwd=tmp_path,
        inputs=[source, source], writable=[output], protected=[source], done=['Valid JSON'])
    task = json.loads(target.read_text())
    assert len(task['inputs']) == 1
    assert task['inputs'][0]['revision'] == f'{source.stat().st_size}:{source.stat().st_mtime_ns}'
    assert task['writable'] == [str(output)]
    assert task['protected'] == [str(source), str(target)]
    assert 'PRIVATE_SOURCE_BODY' not in prompt + target.read_text()
    assert 'PRIVATE_PROVIDER_KEY' not in prompt + target.read_text()
    assert len(target.read_text()) < 1500
    assert str(target) in prompt
    assert '不自行进入下一步' in prompt


def test_missing_optional_inputs_are_explicit_and_do_not_trigger_project_discovery(tmp_path):
    target=tmp_path/'task.json'; source=tmp_path/'not-written-yet.html'
    write_task_context(target, stage='4', objective='Create clip', cwd=tmp_path, inputs=[source, ''], optional_inputs=[source])
    task=json.loads(target.read_text())
    assert task['inputs'] == [{'path': str(source), 'exists': False, 'required': False, 'revision': None}]


def test_segmentation_sdk_uses_only_its_input_and_output_context(tmp_path, monkeypatch):
    import anyio
    from claude_agent_sdk import ResultMessage
    from core.infra.ai import claude_agent
    source=tmp_path/'text/raw.json';source.parent.mkdir()
    original=json.dumps({'content':'First. Second.'})
    source.write_text(original)
    output=source.parent/'segments.json';log=source.parent/'segment-session.jsonl'
    expected=[{'content':'First.','visualizer':'image'},{'content':'Second.','visualizer':'hf'}]
    captured={}

    async def query(*,prompt,options):
        captured.update(prompt=prompt,options=options)
        output.write_text(json.dumps({'segments':expected}))
        yield ResultMessage(subtype='success',duration_ms=0,duration_api_ms=0,is_error=False,num_turns=1,session_id='test')

    monkeypatch.setattr(claude_agent,'query',query)
    monkeypatch.setattr(claude_agent,'build_step1_5_agent_env',lambda **kwargs:{})
    async def run():
        return await claude_agent._run_step1_5_segment_agent_async(raw_json_path=str(source),
            output_json_path=str(output),target_segments=2,session_log_path=str(log),repo_root=str(tmp_path),llm_server='deepseek')
    assert anyio.run(run)==expected
    assert source.read_text()==original
    assert captured['options'].tools==['Read','Write']
    assert captured['options'].cwd==str(source.parent.resolve())
    assert captured['options'].setting_sources==[]
    task=json.loads(log.with_suffix('.task.json').read_text())
    assert task['writable']==[str(output.resolve())]
    assert str(source.resolve()) in task['protected']
    assert '不自行进入下一步' in captured['prompt']
