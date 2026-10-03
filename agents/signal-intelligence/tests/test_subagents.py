import json

import pytest

from intelligence_subagents import SubagentError, SubagentRunner
from subagents.topic_analyst import run as topic_run
from subagents.evidence_researcher import run as research_run
from subagents.draft_writer import run as draft_run


def test_subagent_runner_accepts_valid_json_envelope(tmp_path):
    script = tmp_path / "topic_analyst.py"
    script.write_text("import json,sys\n"
                      "request=json.load(sys.stdin)\n"
                      "print(json.dumps({'status':'success','data':{'ids':request['signal_ids']}}))\n")
    runner = SubagentRunner(directory=tmp_path, timeout=2)
    assert runner.run("topic_analyst", {"signal_ids": [1, 2]}) == {"ids": [1, 2]}


def test_subagent_runner_rejects_unknown_and_malformed_output(tmp_path):
    runner = SubagentRunner(directory=tmp_path, timeout=2)
    with pytest.raises(SubagentError, match="Unknown"):
        runner.run("other", {})
    (tmp_path / "topic_analyst.py").write_text("print('not json')\n")
    with pytest.raises(SubagentError, match="invalid JSON"):
        runner.run("topic_analyst", {"signal_ids": [1]})


def test_subagent_runner_times_out_without_accepting_output(tmp_path):
    (tmp_path / "topic_analyst.py").write_text("import time\ntime.sleep(2)\n")
    runner = SubagentRunner(directory=tmp_path, timeout=0.1)
    with pytest.raises(SubagentError, match="timed out"):
        runner.run("topic_analyst", {"signal_ids": [1]})


def test_each_subagent_has_one_bounded_job_with_ids_only():
    class Store:
        def signal_titles(self, ids):
            return ["Acme releases agent toolkit", "Acme agent toolkit arrives"]

        def get_opportunity(self, id):
            return {"id": id, "label": "Agent toolkit", "evidence_source_item_ids": [3]}

        def source_evidence(self, ids):
            return [{"id": 3, "title": "Agent toolkit", "source_url": "https://example.com/3"}]

        def latest_research(self, id):
            return {"id": 4, "status": "complete", "evidence": [{"id": 5, "claim": "Toolkit released",
                                                                 "source_url": "https://example.com/3"}]}

        def get_brief(self):
            return {"brief": {"voice": "Practical"}}

    class Provider:
        def research(self, opportunity, source_items):
            return {"status": "partial", "summary": "Grounded", "evidence": []}

        def draft(self, opportunity, research, brief, channel, format):
            return {"text": "Draft text", "evidence_ids": [5]}

    store, provider = Store(), Provider()
    assert "agent toolkit" in topic_run({"signal_ids": [1, 2]}, store)["label"].lower()
    assert research_run({"opportunity_id": 7}, store, provider)["summary"] == "Grounded"
    assert draft_run({"opportunity_id": 7, "channel": "x", "format": "reply"},
                     store, provider)["evidence_ids"] == [5]
