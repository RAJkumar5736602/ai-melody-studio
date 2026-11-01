import uuid
import pytest
from songs_service import (
    SongsService,
    create_song,
    get_song,
    list_songs,
    update_song,
    delete_song,
    toggle_like,
    get_quota,
    check_quota,
    increment_quota,
    reset_quota,
)


def test_create_and_get_song():
    sid = str(uuid.uuid4())
    song = create_song(
        title="Summer Breeze",
        prompt="Upbeat acoustic tune",
        lyrics="La la la",
        genre="Acoustic",
        mood="Happy",
        song_id=sid,
        is_liked=False,
    )

    assert song.id == sid
    assert song["title"] == "Summer Breeze"
    assert song.genre == "Acoustic"
    assert song.dict()["lyrics"] == "La la la"

    retrieved = get_song(sid)
    assert retrieved is not None
    assert retrieved.id == sid
    assert retrieved.title == "Summer Breeze"


def test_update_song():
    sid = str(uuid.uuid4())
    create_song(title="Old Title", song_id=sid)

    updated = update_song(sid, title="New Title", genre="Pop", lyrics="Updated lyrics")
    assert updated is not None
    assert updated.title == "New Title"
    assert updated.genre == "Pop"

    fetched = get_song(sid)
    assert fetched.title == "New Title"


def test_toggle_like():
    sid = str(uuid.uuid4())
    create_song(title="Test Song", song_id=sid, is_liked=False)

    song = toggle_like(sid)
    assert song is not None
    assert song.is_liked is True

    song = toggle_like(sid)
    assert song.is_liked is False


def test_delete_song():
    sid = str(uuid.uuid4())
    create_song(title="Song to Delete", song_id=sid)

    assert get_song(sid) is not None
    deleted = delete_song(sid)
    assert deleted is True
    assert get_song(sid) is None

    # Deleting again should return False
    assert delete_song(sid) is False


def test_list_songs_filtering_and_pagination():
    test_tag = str(uuid.uuid4())[:8]
    s1 = create_song(title=f"UniqueAlpha {test_tag}", genre="Rock", is_liked=True)
    s2 = create_song(title=f"UniqueBeta {test_tag}", genre="Jazz", is_liked=False)
    s3 = create_song(title=f"UniqueGamma {test_tag}", genre="Rock", is_liked=True)

    # Search filter
    search_res = list_songs(search=test_tag)
    assert len(search_res) == 3

    # Liked filter
    liked_res = list_songs(liked_only=True, search=test_tag)
    assert len(liked_res) == 2
    assert all(s.is_liked for s in liked_res)

    # Pagination
    page_1 = list_songs(limit=2, offset=0, search=test_tag)
    assert len(page_1) == 2


def test_quota_management():
    test_date = "2099-01-01"
    reset_quota(date_str=test_date, max_quota=3)

    assert check_quota(date_str=test_date, max_quota=3) is True
    q0 = get_quota(date_str=test_date, max_quota=3)
    assert q0.count == 0
    assert q0.remaining == 3

    q1 = increment_quota(date_str=test_date, max_quota=3)
    assert q1.count == 1
    assert q1.remaining == 2

    q2 = increment_quota(date_str=test_date, max_quota=3)
    q3 = increment_quota(date_str=test_date, max_quota=3)

    assert q3.count == 3
    assert q3.remaining == 0
    assert check_quota(date_str=test_date, max_quota=3) is False

    reset_q = reset_quota(date_str=test_date, max_quota=3)
    assert reset_q.count == 0
    assert reset_q.remaining == 3
    assert check_quota(date_str=test_date, max_quota=3) is True


def test_songs_service_class():
    service = SongsService(max_quota=5)
    sid = str(uuid.uuid4())

    s = service.create_song(title="Service Song", song_id=sid)
    assert s.id == sid

    fetched = service.get_song(sid)
    assert fetched.title == "Service Song"

    toggled = service.toggle_like(sid)
    assert toggled.is_liked is True

    quota = service.get_quota("2099-12-31")
    assert quota.max_quota == 5
    assert quota.remaining == 5

    assert service.delete_song(sid) is True
    assert service.get_song(sid) is None
