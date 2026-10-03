import json

from signal_intelligence import main


class FakeService:
    def __init__(self):
        self.turns = []

    def analyze(self, *, days, limit):
        return {"run_id": 7, "opportunities": [], "days": days, "limit": limit}

    def create_chat_session(self):
        return {"id": 1}

    def chat_history(self, id):
        return self.turns

    def append_chat_turn(self, id, role, content):
        self.turns.append({"role": role, "content": content})

    def opportunities(self):
        return {"run_id": 7, "opportunities": []}

    def replace_content(self, id, item):
        return {"id": 9, "replaces_id": id, **item}


def test_cli_returns_one_json_envelope_for_analysis(capsys):
    assert main(["analyze", "--days", "14"], service=FakeService()) == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"status": "success", "data": {"run_id": 7,
                                                    "opportunities": [], "days": 14, "limit": 500}}


def test_cli_rejects_invalid_analysis_window(capsys):
    assert main(["analyze", "--days", "0"], service=FakeService()) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "error"


def test_cli_supports_offline_chat_and_content_replace(tmp_path, capsys):
    service = FakeService()
    assert main(["--offline", "list opportunities"], service=service) == 0
    assert "No opportunities yet" in capsys.readouterr().out
    path = tmp_path / "content.json"
    path.write_text('{"title":"Updated","text":"New angle","channel":"blog"}')
    assert main(["content", "replace", "3", str(path)], service=service) == 0
    assert json.loads(capsys.readouterr().out)["data"]["replaces_id"] == 3
