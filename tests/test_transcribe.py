import io
import sys
import types

import server


def test_transcribe_endpoint_returns_stubbed_text(monkeypatch):
    fake_module = types.ModuleType("spoken_to_signed.audio_to_text.infer")
    fake_module.transcribe_bytes = lambda audio_bytes: "transcripcion de prueba"
    monkeypatch.setitem(sys.modules, "spoken_to_signed.audio_to_text.infer", fake_module)

    client = server.app.test_client()
    response = client.post(
        "/api/transcribe",
        data={"file": (io.BytesIO(b"fake audio bytes"), "sample.webm")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json() == {"text": "transcripcion de prueba"}


def test_transcribe_endpoint_requires_file():
    client = server.app.test_client()
    response = client.post("/api/transcribe", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
    assert response.get_json() == {"error": "No file uploaded"}