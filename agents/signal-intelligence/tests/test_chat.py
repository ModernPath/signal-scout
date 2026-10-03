from intelligence_chat import MAX_TOOL_CALLS, build_tools, chat_reply, load_skills


class FakeService:
    def __init__(self):
        self.turns = []

    def create_chat_session(self):
        return {"id": 9}

    def chat_history(self, session_id):
        assert session_id == 9
        return self.turns[:]

    def append_chat_turn(self, session_id, role, content):
        self.turns.append({"role": role, "content": content})

    def opportunities(self):
        return {"run_id": 2, "opportunities": [{"id": 7, "label": "Agent toolkit",
                                                "total": 74}]}

    def research(self, id):
        raise RuntimeError("Research provider is unavailable")


def test_offline_chat_uses_service_and_persists_bounded_turns():
    service = FakeService()
    first = chat_reply(service, "list opportunities", offline=True)
    assert first.session_id == 9
    assert "Agent toolkit" in first.reply
    assert first.tools_used == ["opportunities"]
    second = chat_reply(service, "research 7", session_id=9, offline=True)
    assert "unavailable" in second.reply.lower()
    assert second.used_llm is False
    assert len(service.turns) == 4


def test_skill_prompt_contains_domain_guidance():
    loaded = load_skills()
    assert "conversation-analysis" in loaded
    assert "evidence-research" in loaded
    assert "content-drafting" in loaded


def test_model_tool_wrappers_enforce_call_budget():
    service = FakeService()
    used = []
    list_opportunities = build_tools(service, used)[0]
    for _ in range(MAX_TOOL_CALLS):
        assert list_opportunities()["run_id"] == 2
    assert list_opportunities()["error"] == "Tool call limit reached"
    assert len(used) == MAX_TOOL_CALLS


def test_offline_chat_can_inspect_knowledge_through_the_service():
    class Knowledge(FakeService):
        def search_knowledge(self,query,*,semantic):
            assert semantic is False
            assert query=='action verification'
            return dict(mode='lexical',coverage=1,hits=[dict(title='Prior',passage='Verify actions before execution',chunk_id=7)])
    result=chat_reply(Knowledge(),'search knowledge action verification',offline=True)
    assert 'Verify actions before execution' in result.reply
    assert result.tools_used==['search_knowledge']
