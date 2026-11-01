import logging
from pathlib import Path
import pytest
from core_config.core_config import Settings, get_settings, setup_logging, get_logger


def test_default_settings(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    s = get_settings()
    assert s.APP_NAME == "AI Melody Studio"
    assert s.GEMINI_API_KEY == ""
    assert s.DEMO_MODE is True
    assert s.MAX_DAILY_QUOTA == 10
    assert "ai_melody_studio.db" in s.DATABASE_URL


def test_demo_mode_behavior(monkeypatch):
    # With API key set and DEMO_MODE unset, DEMO_MODE should be False
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.delenv("DEMO_MODE", raising=False)
    s = get_settings()
    assert s.DEMO_MODE is False

    # Explicitly set DEMO_MODE to true
    monkeypatch.setenv("DEMO_MODE", "true")
    s2 = get_settings()
    assert s2.DEMO_MODE is True

    # Explicitly set DEMO_MODE to false with missing API key
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("DEMO_MODE", "0")
    s3 = get_settings()
    assert s3.DEMO_MODE is False


def test_custom_env_variables(monkeypatch):
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("MAX_DAILY_QUOTA", "25")

    s = get_settings()
    assert s.PORT == 9090
    assert s.HOST == "127.0.0.1"
    assert s.MAX_DAILY_QUOTA == 25


def test_ensure_directories(tmp_path, monkeypatch):
    audio_dir = tmp_path / "audio_files"
    image_dir = tmp_path / "image_files"

    monkeypatch.setenv("AUDIO_DIR", str(audio_dir))
    monkeypatch.setenv("IMAGE_DIR", str(image_dir))

    s = get_settings()
    assert not audio_dir.exists()
    assert not image_dir.exists()

    s.ensure_directories()

    assert audio_dir.exists() and audio_dir.is_dir()
    assert image_dir.exists() and image_dir.is_dir()


def test_setup_logging_and_get_logger():
    logger = setup_logging("DEBUG")
    assert logger.level == logging.DEBUG

    fetched_logger = get_logger("ai_melody_studio")
    assert fetched_logger is logger

    custom_logger = get_logger("ai_melody_studio.submodule")
    assert custom_logger.name == "ai_melody_studio.submodule"
