from utils.opencode_go import get_opencode_go_headers, is_opencode_go


def test_non_go_endpoint_has_no_headers():
    assert not is_opencode_go("https://opencode.ai/zen/v1")
    assert get_opencode_go_headers("https://opencode.ai/zen/v1") == {}


def test_go_endpoint_has_session_and_user_agent(monkeypatch):
    monkeypatch.setenv("OPENCODE_USER_AGENT", "bettafish-test/1.0")
    headers = get_opencode_go_headers("https://opencode.ai/zen/go/v1/")
    assert headers["x-opencode-session"]
    assert headers["User-Agent"] == "bettafish-test/1.0"
