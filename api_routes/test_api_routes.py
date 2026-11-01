import pytest
from fastapi.testclient import TestClient

import songs_service
from api_routes.api_routes import app


@pytest.fixture(autouse=True)
def reset_state():
    songs_service.reset_quota()
    # Clean up created test songs if possible
    existing = songs_service.list_songs(limit=100)
    for s in existing:
        s_id = s.get("id") if isinstance(s, dict) else getattr(s, "id", None)
        if s_id:
            try:
                songs_service.delete_song(s_id)
            except Exception:
                pass


def test_get_quota():
    client = TestClient(app)
    response = client.get("/api/quota")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data or "remaining" in data or "max_quota" in data or "date" in data


def test_generate_song_success():
    client = TestClient(app)
    payload = {
        "prompt": "synthwave upbeat track",
        "genre": "Synthwave",
        "mood": "Energetic",
        "lyrics": "Neon lights shining bright",
        "title": "Neon Dreams"
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 201
    song = response.json()
    assert song["title"] == "Neon Dreams"
    assert song["prompt"] == "synthwave upbeat track"
    song_id = song["id"]

    # Retrieve song to check background completion
    get_res = client.get(f"/api/songs/{song_id}")
    assert get_res.status_code == 200
    updated_song = get_res.json()
    assert updated_song["status"] == "completed"
    assert updated_song["audio_path"] != ""


def test_generate_song_quota_exceeded(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(songs_service, "check_quota", lambda *args, **kwargs: False)

    payload = {"prompt": "test prompt"}
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 429
    assert "quota" in response.json()["detail"].lower()


def test_list_and_get_songs():
    client = TestClient(app)

    # Generate two songs
    res1 = client.post("/api/generate", json={"prompt": "chill beats", "title": "Chill 1"})
    res2 = client.post("/api/generate", json={"prompt": "rock guitar", "title": "Rock 2"})

    song1_id = res1.json()["id"]
    song2_id = res2.json()["id"]

    list_res = client.get("/api/songs")
    assert list_res.status_code == 200
    songs = list_res.json()
    assert len(songs) >= 2

    # Get by ID
    get_res = client.get(f"/api/songs/{song1_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Chill 1"

    # Get non-existent
    bad_res = client.get("/api/songs/non-existent-id")
    assert bad_res.status_code == 404


def test_delete_song():
    client = TestClient(app)
    res = client.post("/api/generate", json={"prompt": "to be deleted"})
    song_id = res.json()["id"]

    del_res = client.delete(f"/api/songs/{song_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/api/songs/{song_id}")
    assert get_res.status_code == 404

    # Delete non-existent
    del_bad = client.delete(f"/api/songs/{song_id}")
    assert del_bad.status_code == 404


def test_toggle_like_and_update_song():
    client = TestClient(app)
    res = client.post("/api/generate", json={"prompt": "jazz piano", "title": "Jazz Vibe"})
    song_id = res.json()["id"]

    # Toggle like
    like_res = client.post(f"/api/songs/{song_id}/like")
    assert like_res.status_code == 200
    assert like_res.json()["is_liked"] is True

    # Patch song
    patch_res = client.patch(f"/api/songs/{song_id}", json={"title": "Updated Jazz Vibe"})
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated Jazz Vibe"


def test_remake_song():
    client = TestClient(app)
    orig_res = client.post("/api/generate", json={
        "prompt": "acoustic guitar",
        "genre": "Acoustic",
        "mood": "Calm",
        "title": "Morning Breeze"
    })
    orig_id = orig_res.json()["id"]

    remake_res = client.post(f"/api/remake/{orig_id}", json={
        "mood": "Upbeat"
    })
    assert remake_res.status_code == 201
    remake = remake_res.json()
    assert remake["id"] != orig_id
    assert remake["genre"] == "Acoustic"
    assert remake["mood"] == "Upbeat"
    assert "Morning Breeze" in remake["title"]

    # Remake non-existent song
    bad_remake = client.post("/api/remake/invalid-id", json={})
    assert bad_remake.status_code == 404
