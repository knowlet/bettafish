from SystemOne import decisions


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []
    def evaluate(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def test_media_provider_filters_bocha_only_tools(monkeypatch):
    fake = FakeClient({"answers": {"search_tool": {"choice": "search_last_week"}}})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    routed = decisions.choose_media_search_tool(
        input_data={"title": "最近趋势", "content": "过去一周"},
        generated_query="最近趋势", phase="initial", provider="AnspireAPI",
    )
    assert routed["search_tool"] == "search_last_week"
    criteria = fake.calls[0]["questions"]["search_tool"]["criteria"]
    assert "web_search_only" not in criteria
    assert "search_for_structured_data" not in criteria


def test_insight_plan_batches_parameters(monkeypatch):
    fake = FakeClient({"answers": {
        "search_tool": {"choice": "search_topic_on_platform"},
        "platform": {"choice": "weibo"},
        "time_period": {"choice": "week"},
        "enable_sentiment": {"noul": 0.8},
    }})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    plan = decisions.choose_insight_search_plan(
        input_data={"title": "微博舆论", "content": "分析微博用户反应"},
        generated_query="事件 微博", phase="initial",
    )
    assert plan["search_tool"] == "search_topic_on_platform"
    assert plan["platform"] == "weibo"
    assert plan["enable_sentiment"] is True
    assert len(fake.calls) == 1
    assert set(fake.calls[0]["questions"]) == {"search_tool", "platform", "time_period", "enable_sentiment"}
    tool_criteria = fake.calls[0]["questions"]["search_tool"]["criteria"]
    assert "analyze_sentiment" not in tool_criteria


def test_evidence_triage_uses_batched_scores(monkeypatch):
    answers = {}
    for i in range(3):
        answers[f"r{i}_relevance"] = {"score": float(i)}
        answers[f"r{i}_evidence"] = {"score": float(i)}
        answers[f"r{i}_novelty"] = {"score": float(i)}
    fake = FakeClient({"answers": answers})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    ranked = decisions.triage_evidence(
        query="q", section={"title": "s"},
        results=[{"title": "a", "content": "a"}, {"title": "b", "content": "b"}, {"title": "c", "content": "c"}],
        decision_id="test.evidence", max_results=2,
    )
    assert [x["title"] for x in ranked] == ["c", "b"]
    assert len(fake.calls[0]["questions"]) == 9


def test_forum_host_gate(monkeypatch):
    fake = FakeClient({"answers": {"host_needed": {"noul": 0.2}, "host_reason": {"choice": "none"}}})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    assert decisions.decide_forum_host(["[00:00:00] [QUERY] ok"])["needed"] is False


def test_word_budget_is_deterministic_after_scores(monkeypatch):
    fake = FakeClient({"answers": {
        "s0_importance": {"score": 3.0}, "s0_evidence": {"score": 3.0}, "s0_complexity": {"score": 2.0},
        "s1_importance": {"score": 1.0}, "s1_evidence": {"score": 1.0}, "s1_complexity": {"score": 1.0},
    }})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    plan = decisions.plan_word_budget(
        sections=[{"chapterId": "S1", "title": "核心", "outline": ["a"]}, {"chapterId": "S2", "title": "附录", "outline": []}],
        query="q", reports={"query": "x"}, forum_logs="", total_words=10000,
    )
    assert plan["decision_source"] == "system_one"
    assert sum(x["targetWords"] for x in plan["chapters"]) == 10000
    assert plan["chapters"][0]["targetWords"] > plan["chapters"][1]["targetWords"]



def test_layout_controls_enforce_single_swot_and_pest(monkeypatch):
    fake = FakeClient({"answers": {
        "s0_swot": {"noul": 0.9}, "s0_pest": {"noul": 0.2},
        "s1_swot": {"noul": 0.8}, "s1_pest": {"noul": 0.95},
    }})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    design = {
        "tocPlan": [
            {"chapterId": "S1", "display": "一"},
            {"chapterId": "S2", "display": "二"},
        ]
    }
    result = decisions.apply_layout_controls(
        design=design,
        sections=[
            {"chapterId": "S1", "title": "内部能力"},
            {"chapterId": "S2", "title": "宏观环境"},
        ],
        query="分析公司战略",
    )
    assert result["tocPlan"][0]["allowSwot"] is True
    assert result["tocPlan"][1]["allowSwot"] is False
    assert result["tocPlan"][1]["allowPest"] is True
    assert result["layoutDecisionSource"] == "system_one"



def test_keyword_expansion_gate(monkeypatch):
    fake = FakeClient({"answers": {"expand_keywords": {"noul": 0.12}}})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    assert decisions.should_expand_insight_keywords("广州大学城随机捅人") is False

    fake.result = {"answers": {"expand_keywords": {"noul": 0.91}}}
    assert decisions.should_expand_insight_keywords(
        "品牌舆情管理未来趋势", "寻找贴近网民语言的同义词"
    ) is True



def test_evidence_triage_partial_response_fails_open(monkeypatch):
    fake = FakeClient({"answers": {
        "r0_relevance": {"score": 3.0},
        "r0_evidence": {"score": 3.0},
        "r0_novelty": {"score": 3.0},
        "r1_relevance": {"score": 3.0},
        "r1_evidence": {"score": 3.0},
        # r1_novelty intentionally missing
        "r2_relevance": {"score": 3.0},
        "r2_evidence": {"score": 3.0},
        "r2_novelty": {"score": 3.0},
    }})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    original = [
        {"title": "first", "content": "a"},
        {"title": "second", "content": "b"},
        {"title": "third", "content": "c"},
    ]
    ranked = decisions.triage_evidence(
        query="q",
        section={"title": "s"},
        results=original,
        decision_id="test.partial",
        max_results=2,
    )
    assert [item["title"] for item in ranked] == ["first", "second"]


def test_word_budget_small_total_still_sums_exactly(monkeypatch):
    fake = FakeClient({"answers": {
        "s0_importance": {"score": 3.0}, "s0_evidence": {"score": 3.0}, "s0_complexity": {"score": 3.0},
        "s1_importance": {"score": 2.0}, "s1_evidence": {"score": 2.0}, "s1_complexity": {"score": 2.0},
        "s2_importance": {"score": 1.0}, "s2_evidence": {"score": 1.0}, "s2_complexity": {"score": 1.0},
    }})
    monkeypatch.setattr(decisions, "get_system_one_client", lambda: fake)
    plan = decisions.plan_word_budget(
        sections=[
            {"chapterId": "S1", "title": "A"},
            {"chapterId": "S2", "title": "B"},
            {"chapterId": "S3", "title": "C"},
        ],
        query="q",
        reports={},
        forum_logs="",
        total_words=500,
    )
    targets = [chapter["targetWords"] for chapter in plan["chapters"]]
    assert sum(targets) == 500
    assert all(target >= 0 for target in targets)
