from SystemOne import decisions


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def evaluate(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def test_extract_explicit_date_range():
    assert decisions.extract_explicit_date_range(
        "研究 2026-09-01 到 2026-09-05 的报道"
    ) == ("2026-09-01", "2026-09-05")
    assert decisions.extract_explicit_date_range("只有 2026-09-01") is None


def test_query_tool_choice_and_date(monkeypatch):
    fake = FakeClient(
        {"answers": {"search_tool": {"choice": "search_news_by_date", "confidence": 0.91}}}
    )
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    routed = decisions.choose_query_search_tool(
        input_data={"title": "历史事件", "content": "比较 2026-09-01 到 2026-09-05 的报道"},
        generated_query="历史事件 报道",
        phase="initial",
    )
    assert routed["search_tool"] == "search_news_by_date"
    assert routed["start_date"] == "2026-09-01"
    assert routed["end_date"] == "2026-09-05"


def test_low_confidence_choice_falls_back(monkeypatch):
    fake = FakeClient(
        {"answers": {"search_tool": {"choice": "deep_search_news", "confidence": 0.2}}}
    )
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    assert decisions.choose_query_search_tool(
        input_data={"title": "主题", "content": "一般研究"},
        generated_query="主题",
        phase="initial",
    ) is None


def test_reflection_gate(monkeypatch):
    monkeypatch.setenv("SYSTEM_ONE_STOP_THRESHOLD", "0.30")
    fake = FakeClient(
        {"answers": {"continue_research": {"noul": 0.12, "confidence": 0.8}}}
    )
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    assert decisions.should_continue_research({"paragraph_latest_state": "完整"}) is False

    fake.result = {"answers": {"continue_research": {"noul": 0.72, "confidence": 0.8}}}
    assert decisions.should_continue_research({"paragraph_latest_state": "缺资料"}) is True


def test_report_template_choice(monkeypatch):
    fake = FakeClient(
        {"answers": {"report_template": {"choice": "template_1", "confidence": 0.88}}}
    )
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    templates = [
        {"name": "A", "description": "品牌", "content": "# A"},
        {"name": "B", "description": "危机", "content": "# B"},
    ]
    result = decisions.choose_report_template(
        query="危机事件分析", reports=[], forum_logs="", available_templates=templates
    )
    assert result["template_name"] == "B"
    assert result["decision_source"] == "system_one"
