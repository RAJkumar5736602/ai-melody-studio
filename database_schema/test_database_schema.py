from datetime import datetime
import pytest

from database_schema import (
    Song,
    UserQuota,
    get_engine,
    create_db_and_tables,
    init_db,
    get_session,
)


def test_song_model_instantiation():
    song = Song(
        title="Synthwave Beats",
        prompt="A energetic synthwave track with heavy bass",
        genre="Synthwave",
        mood="Energetic",
    )
    assert song.id is not None
    assert song.title == "Synthwave Beats"
    assert song.prompt == "A energetic synthwave track with heavy bass"
    assert song.genre == "Synthwave"
    assert song.mood == "Energetic"
    assert song.is_liked is False
    assert song.status == "completed"

    song_dict = song.dict()
    assert song_dict["id"] == song.id
    assert song_dict["title"] == "Synthwave Beats"
    assert song_dict["genre"] == "Synthwave"


def test_user_quota_model_instantiation():
    quota = UserQuota(date="2026-03-30", count=2, max_quota=10)
    assert quota.date == "2026-03-30"
    assert quota.count == 2
    assert quota.max_quota == 10

    quota_dict = quota.dict()
    assert quota_dict["date"] == "2026-03-30"
    assert quota_dict["count"] == 2


def test_db_init_and_session(tmp_path):
    db_file = tmp_path / "test.db"
    db_url = f"sqlite:///{db_file}"

    engine = get_engine(db_url)
    init_db(engine)

    with get_session(engine) as session:
        song = Song(
            title="Acoustic Sunrise",
            prompt="Soft guitar melody",
            genre="Acoustic",
            mood="Relaxing",
            audio_path="/audio/1.mp3",
        )
        session.add(song)
        session.commit()

        song_id = song.id

    with get_session(engine) as session:
        fetched_song = session.get(Song, song_id)
        assert fetched_song is not None
        assert fetched_song.title == "Acoustic Sunrise"
        assert fetched_song.audio_path == "/audio/1.mp3"

        if hasattr(session, "query"):
            songs = session.query(Song).all()
            assert len(songs) >= 1


def test_song_update_and_delete(tmp_path):
    db_file = tmp_path / "test_crud.db"
    db_url = f"sqlite:///{db_file}"
    engine = get_engine(db_url)
    create_db_and_tables(engine)

    song = Song(title="Test Song", prompt="Test Prompt")
    with get_session(engine) as session:
        session.add(song)
        session.commit()
        song_id = song.id

    with get_session(engine) as session:
        s = session.get(Song, song_id)
        assert s is not None
        s.is_liked = True
        session.add(s)
        session.commit()

    with get_session(engine) as session:
        s = session.get(Song, song_id)
        assert s.is_liked is True

    with get_session(engine) as session:
        s = session.get(Song, song_id)
        session.delete(s)
        session.commit()

    with get_session(engine) as session:
        s = session.get(Song, song_id)
        assert s is None


def test_user_quota_crud(tmp_path):
    db_file = tmp_path / "test_quota.db"
    db_url = f"sqlite:///{db_file}"
    engine = get_engine(db_url)
    create_db_and_tables(engine)

    quota = UserQuota(date="2026-03-30", count=1, max_quota=10)
    with get_session(engine) as session:
        session.add(quota)
        session.commit()
        quota_id = quota.id

    assert quota_id is not None

    with get_session(engine) as session:
        q = session.get(UserQuota, quota_id)
        assert q is not None
        assert q.count == 1

        q.count += 1
        session.add(q)
        session.commit()

    with get_session(engine) as session:
        q = session.get(UserQuota, quota_id)
        assert q.count == 2
