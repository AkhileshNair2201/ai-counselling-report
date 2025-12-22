from my_project.main import app


def test_app_instance() -> None:
    assert app.title == "Audio Ingest API"
