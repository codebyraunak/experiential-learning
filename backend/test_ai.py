from app.ai import FALLBACK_SUGGESTION, categorize_complaint


def test_ai_falls_back_when_gemini_key_is_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert categorize_complaint("Water leak", "Pipe is leaking") == FALLBACK_SUGGESTION


def test_ai_falls_back_when_gemini_request_fails(monkeypatch):
    import httpx
    import app.ai

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-secret")

    def fail_request(*args, **kwargs):
        raise httpx.ConnectError("test connection failure")

    monkeypatch.setattr(app.ai.httpx, "post", fail_request)

    assert categorize_complaint("Water leak", "Pipe is leaking") == FALLBACK_SUGGESTION
