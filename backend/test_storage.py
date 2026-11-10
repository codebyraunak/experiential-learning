import httpx
import pytest

from app import uploads


@pytest.fixture(autouse=True)
def clear_supabase_environment(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)


def test_local_storage_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOAD_DIR", tmp_path)

    filename = uploads.save_image(b"image-bytes", "image/png")

    assert filename.endswith(".png")
    assert uploads.get_image(filename) == (b"image-bytes", "image/png")
    uploads.delete_image(filename)
    assert uploads.get_image(filename) is None


def test_supabase_storage_upload_retrieve_and_delete(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "campusfix-complaint-photos")
    requests = []

    def fake_request(method, url, **kwargs):
        requests.append((method, url, kwargs))
        content = b"stored-image" if method == "GET" else b""
        return httpx.Response(200, content=content)

    monkeypatch.setattr(uploads.httpx, "request", fake_request)

    filename = uploads.save_image(b"image-bytes", "image/png")
    assert uploads.get_image(filename) == (b"stored-image", "image/png")
    uploads.delete_image(filename)

    assert [request[0] for request in requests] == ["POST", "GET", "DELETE"]
    assert requests[0][1].endswith(f"/campusfix-complaint-photos/{filename}")
    assert requests[0][2]["content"] == b"image-bytes"
    assert requests[0][2]["headers"]["Content-Type"] == "image/png"
    assert requests[0][2]["headers"]["x-upsert"] == "false"
    assert requests[0][2]["headers"]["apikey"] == "test-service-role-key"
    assert requests[0][2]["headers"]["Authorization"] == "Bearer test-service-role-key"
    assert requests[2][2]["json"] == {"prefixes": [filename]}
    assert "test-service-role-key" not in requests[0][1]


def test_supabase_missing_object_returns_none(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setattr(
        uploads.httpx,
        "request",
        lambda *args, **kwargs: httpx.Response(404),
    )

    assert uploads.get_image("0" * 32 + ".jpg") is None


def test_partial_supabase_configuration_does_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOAD_DIR", tmp_path)
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")

    with pytest.raises(RuntimeError, match="must both be configured"):
        uploads.save_image(b"image-bytes", "image/png")
    assert list(tmp_path.iterdir()) == []


def test_production_without_supabase_storage_fails_closed(monkeypatch):
    monkeypatch.setenv("RENDER", "true")

    with pytest.raises(RuntimeError, match="must be configured for production"):
        uploads.save_image(b"image-bytes", "image/png")


def test_invalid_photo_names_are_not_read_or_deleted(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(uploads, "UPLOAD_DIR", upload_dir)
    outside_file = tmp_path / "outside.png"
    outside_file.write_bytes(b"do not touch")
    uploads.delete_image("../outside.png")

    assert uploads.get_image("../outside.png") is None
    assert outside_file.read_bytes() == b"do not touch"
