import pytest
from pathlib import Path
from storage_manager.storage_manager import (
    StorageManager,
    save_audio,
    save_image,
    get_audio_path,
    get_image_path,
    read_audio,
    read_image,
    delete_audio,
    delete_image,
    delete_song_files,
    audio_exists,
    image_exists,
)


@pytest.fixture
def temp_sm(tmp_path):
    audio_dir = tmp_path / "audio"
    image_dir = tmp_path / "images"
    return StorageManager(audio_dir=audio_dir, image_dir=image_dir)


def test_storage_manager_init(tmp_path):
    audio_dir = tmp_path / "a"
    image_dir = tmp_path / "i"
    sm = StorageManager(audio_dir=audio_dir, image_dir=image_dir)
    assert audio_dir.exists()
    assert image_dir.exists()


def test_save_and_read_audio(temp_sm):
    data = b"fake mp3 audio data"
    song_id = "test-song-123"

    saved_path_str = temp_sm.save_audio(data, song_id)
    assert Path(saved_path_str).exists()
    assert temp_sm.audio_exists(song_id)

    read_data = temp_sm.read_audio(song_id)
    assert read_data == data


def test_save_and_read_image(temp_sm):
    data = b"fake png image data"
    song_id = "test-song-456"

    saved_path_str = temp_sm.save_image(data, song_id)
    assert Path(saved_path_str).exists()
    assert temp_sm.image_exists(song_id)

    read_data = temp_sm.read_image(song_id)
    assert read_data == data


def test_custom_extensions(temp_sm):
    audio_data = b"wav data"
    saved_audio = temp_sm.save_audio(audio_data, "song-wav", extension="wav")
    assert saved_audio.endswith(".wav")
    assert temp_sm.get_audio_path("song-wav").suffix == ".wav"

    image_data = b"jpg data"
    saved_image = temp_sm.save_image(image_data, "cover-jpg", extension="jpg")
    assert saved_image.endswith(".jpg")
    assert temp_sm.get_image_path("cover-jpg").suffix == ".jpg"


def test_existing_filename_with_ext(temp_sm):
    data = b"audio bytes"
    temp_sm.save_audio(data, "song_with_ext.mp3")
    assert temp_sm.audio_exists("song_with_ext.mp3")
    assert temp_sm.audio_exists("song_with_ext")
    assert temp_sm.read_audio("song_with_ext.mp3") == data


def test_read_non_existent_raises(temp_sm):
    with pytest.raises(FileNotFoundError):
        temp_sm.read_audio("non-existent-id")

    with pytest.raises(FileNotFoundError):
        temp_sm.read_image("non-existent-id")


def test_delete_audio_and_image(temp_sm):
    song_id = "song-to-delete"
    temp_sm.save_audio(b"audio", song_id)
    temp_sm.save_image(b"image", song_id)

    assert temp_sm.audio_exists(song_id)
    assert temp_sm.image_exists(song_id)

    res = temp_sm.delete_song_files(song_id)
    assert res == {"audio": True, "image": True}

    assert not temp_sm.audio_exists(song_id)
    assert not temp_sm.image_exists(song_id)


def test_delete_non_existent_returns_false(temp_sm):
    assert not temp_sm.delete_audio("ghost")
    assert not temp_sm.delete_image("ghost")


def test_path_traversal_prevention(temp_sm):
    traversal_id = "../../etc/passwd"

    saved_path = temp_sm.save_audio(b"safe", traversal_id)
    assert Path(saved_path).parent == temp_sm.audio_dir.resolve()
    assert Path(saved_path).name == "passwd.mp3"

    with pytest.raises(ValueError):
        temp_sm.save_audio(b"data", "")


def test_module_level_helpers(tmp_path, monkeypatch):
    sm = StorageManager(audio_dir=tmp_path / "maudio", image_dir=tmp_path / "mimage")
    monkeypatch.setattr("storage_manager.storage_manager._default_storage_manager", sm)

    a_path = save_audio(b"m_audio", "m_song")
    i_path = save_image(b"m_image", "m_song")

    assert audio_exists("m_song")
    assert image_exists("m_song")
    assert read_audio("m_song") == b"m_audio"
    assert read_image("m_song") == b"m_image"

    del_res = delete_song_files("m_song")
    assert del_res == {"audio": True, "image": True}
    assert not audio_exists("m_song")
