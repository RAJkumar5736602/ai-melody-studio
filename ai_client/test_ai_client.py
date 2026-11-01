import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
import core_config
from ai_client.ai_client import AIClient
from ai_client.demo_generator import generate_demo_song


@pytest.fixture
def custom_settings(tmp_path):
    settings = core_config.get_settings()
    settings.AUDIO_DIR = tmp_path / "audio"
    settings.IMAGE_DIR = tmp_path / "images"
    settings.GEMINI_API_KEY = "test-api-key"
    settings._demo_mode_env = "false"
    return settings


def test_generate_demo_song_directly(tmp_path):
    settings = core_config.get_settings()
    settings.AUDIO_DIR = tmp_path / "audio"
    settings.IMAGE_DIR = tmp_path / "images"

    res = generate_demo_song(
        prompt="A relaxing acoustic guitar melody",
        genre="Acoustic",
        mood="Calm",
        settings=settings,
    )

    assert res["is_demo"] is True
    assert res["genre"] == "Acoustic"
    assert res["mood"] == "Calm"
    assert Path(res["audio_path"]).exists()
    assert Path(res["image_path"]).exists()


def test_ai_client_demo_mode_generation(tmp_path):
    settings = core_config.get_settings()
    settings.AUDIO_DIR = tmp_path / "audio"
    settings.IMAGE_DIR = tmp_path / "images"
    settings.GEMINI_API_KEY = ""

    client = AIClient(settings=settings)
    res = asyncio.run(client.generate_song(prompt="Synthwave beat"))

    assert res["is_demo"] is True
    assert "Synthwave" in res["prompt"]
    assert Path(res["audio_path"]).exists()


def test_ai_client_custom_lyrics_and_title(tmp_path):
    settings = core_config.get_settings()
    settings.AUDIO_DIR = tmp_path / "audio"
    settings.IMAGE_DIR = tmp_path / "images"

    client = AIClient(settings=settings)
    res = asyncio.run(
        client.generate_song(
            prompt="Jazz night",
            lyrics="Custom lyrics here",
            title="Custom Jazz Title",
        )
    )

    assert res["title"] == "Custom Jazz Title"
    assert res["lyrics"] == "Custom lyrics here"


def test_ai_client_remake_song(tmp_path):
    settings = core_config.get_settings()
    settings.AUDIO_DIR = tmp_path / "audio"
    settings.IMAGE_DIR = tmp_path / "images"

    client = AIClient(settings=settings)
    res = asyncio.run(
        client.remake_song(
            original_prompt="Piano ballad",
            original_genre="Classical",
            original_mood="Melancholy",
            modification_prompt="Add upbeat drums",
            original_title="Original Ballad",
        )
    )

    assert "Remix: Add upbeat drums" in res["prompt"]
    assert res["title"] == "Original Ballad (Remix)"


def test_ai_client_gemini_fallback_on_error(custom_settings):
    client = AIClient(settings=custom_settings)

    with patch.object(client, "_call_gemini_api", side_effect=RuntimeError("API quota exceeded")):
        res = asyncio.run(client.generate_song(prompt="Test fallback"))

    assert res["is_demo"] is True
    assert Path(res["audio_path"]).exists()


def test_ai_client_handles_string_paths_in_settings(tmp_path):
    settings = core_config.get_settings()
    settings.AUDIO_DIR = str(tmp_path / "audio_str")
    settings.IMAGE_DIR = str(tmp_path / "images_str")

    client = AIClient(settings=settings)
    with patch.object(client, "_call_gemini_api", side_effect=RuntimeError("API quota exceeded")):
        res = asyncio.run(client.generate_song(prompt="Test string paths"))

    assert res["is_demo"] is True
    assert Path(res["audio_path"]).exists()
