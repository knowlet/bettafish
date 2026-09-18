import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def function_node(path: str, function_name: str, class_name: str | None = None):
    tree = ast.parse(source(path))
    scope = tree.body
    if class_name:
        cls = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        scope = cls.body
    return next(
        node for node in scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )


def call_name(call: ast.Call) -> str | None:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def call_lines(node) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = call_name(child)
        if name:
            result.setdefault(name, []).append(child.lineno)
    return result


def returns_name(node, name: str) -> bool:
    return any(
        isinstance(child, ast.Return)
        and isinstance(child.value, ast.Name)
        and child.value.id == name
        for child in ast.walk(node)
    )


def test_insight_runtime_uses_system_one_plan_and_stop_gate():
    search_run = function_node(
        "InsightEngine/nodes/search_node.py", "run", "FirstSearchNode"
    )
    reflection_loop = function_node(
        "InsightEngine/agent.py", "_reflection_loop", "DeepSearchAgent"
    )
    assert "choose_insight_search_plan" in call_lines(search_run)
    assert "should_continue_research" in call_lines(reflection_loop)

    # The exact decision id is part of the behavior contract, not a log message.
    decision_ids = [
        keyword.value.value
        for child in ast.walk(reflection_loop)
        if isinstance(child, ast.Call) and call_name(child) == "should_continue_research"
        for keyword in child.keywords
        if keyword.arg == "decision_id"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    ]
    assert "insight.reflection.continue" in decision_ids

    agent = source("InsightEngine/agent.py")
    assert 'search_kwargs["enable_sentiment"]' in agent


def test_keyword_optimizer_gates_llm_expansion_by_control_flow():
    run = function_node(
        "InsightEngine/tools/keyword_optimizer.py",
        "optimize_keywords",
        "KeywordOptimizer",
    )
    calls = call_lines(run)
    assert "should_expand_insight_keywords" in calls
    assert "_call_qwen_api" in calls
    assert min(calls["should_expand_insight_keywords"]) < min(calls["_call_qwen_api"])

    gate_if = next(
        child for child in ast.walk(run)
        if isinstance(child, ast.If)
        and any(
            isinstance(name, ast.Name) and name.id == "expand_keywords"
            for name in ast.walk(child.test)
        )
    )
    assert any(isinstance(child, ast.Return) for child in ast.walk(gate_if))


def test_forum_runtime_gates_host_generation_before_llm():
    method = function_node("ForumEngine/monitor.py", "_trigger_host_speech", "LogMonitor")
    calls = call_lines(method)
    assert "decide_forum_host" in calls
    assert "generate_host_speech" in calls
    assert min(calls["decide_forum_host"]) < min(calls["generate_host_speech"])

    # A negative Jev decision must have an early return before host generation.
    assert any(
        isinstance(child, ast.Return)
        and child.lineno < min(calls["generate_host_speech"])
        for child in ast.walk(method)
    )


def test_word_budget_prefers_system_one_and_returns_it_directly():
    run = function_node("ReportEngine/nodes/word_budget_node.py", "run", "WordBudgetNode")
    calls = call_lines(run)
    assert "plan_word_budget" in calls
    assert "stream_invoke_to_string" in calls
    assert min(calls["plan_word_budget"]) < min(calls["stream_invoke_to_string"])

    jev_if = next(
        child for child in ast.walk(run)
        if isinstance(child, ast.If)
        and isinstance(child.test, ast.Name)
        and child.test.id == "system_one_plan"
    )
    assert returns_name(jev_if, "system_one_plan")


def test_document_layout_applies_bounded_controls_after_generation():
    run = function_node(
        "ReportEngine/nodes/document_layout_node.py", "run", "DocumentLayoutNode"
    )
    calls = call_lines(run)
    assert "stream_invoke_to_string" in calls
    assert "apply_layout_controls" in calls
    assert min(calls["stream_invoke_to_string"]) < min(calls["apply_layout_controls"])
