import datetime
import uuid
from typing import Dict, List, Optional, Any, Union

try:
    import database_schema
except ImportError:
    database_schema = None

import storage_manager

DEFAULT_MAX_QUOTA = 10


class SongData(dict):
    """
    Dictionary wrapper supporting both dict key and attribute access
    as well as .dict() serialization helper for API compatibility.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in list(self.items()):
            if isinstance(v, datetime.datetime):
                self[k] = v.isoformat()

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(f"'SongData' object has no attribute '{item}'")

    def __setattr__(self, key, value):
        if isinstance(value, datetime.datetime):
            value = value.isoformat()
        self[key] = value

    def dict(self) -> dict:
        return dict(self)


class QuotaData(dict):
    """
    Dictionary wrapper for user daily quota info.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(f"'QuotaData' object has no attribute '{item}'")

    def __setattr__(self, key, value):
        self[key] = value

    def dict(self) -> dict:
        return dict(self)


_IN_MEMORY_SONGS: Dict[str, SongData] = {}
_IN_MEMORY_QUOTAS: Dict[str, QuotaData] = {}


def _get_today_date_str() -> str:
    return datetime.date.today().isoformat()


def _format_song(song_obj: Any) -> SongData:
    if isinstance(song_obj, SongData):
        return song_obj
    if isinstance(song_obj, dict):
        return SongData(song_obj)

    if hasattr(song_obj, "dict") and callable(getattr(song_obj, "dict")):
        try:
            return SongData(song_obj.dict())
        except Exception:
            pass

    data = {}
    fields = [
        "id", "title", "prompt", "lyrics", "genre", "mood",
        "audio_path", "image_path", "is_liked", "status", "created_at"
    ]
    for attr in fields:
        val = getattr(song_obj, attr, None)
        if isinstance(val, datetime.datetime):
            val = val.isoformat()
        data[attr] = val
    return SongData(data)


def create_song(
    title: str = "Untitled",
    prompt: str = "",
    lyrics: str = "",
    genre: str = "",
    mood: str = "",
    song_id: Optional[str] = None,
    status: str = "completed",
    audio_path: str = "",
    image_path: str = "",
    is_liked: bool = False,
    db: Optional[Any] = None
) -> SongData:
    sid = song_id or str(uuid.uuid4())
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    song_data = SongData({
        "id": sid,
        "title": title or "Untitled",
        "prompt": prompt,
        "lyrics": lyrics,
        "genre": genre,
        "mood": mood,
        "audio_path": audio_path,
        "image_path": image_path,
        "is_liked": bool(is_liked),
        "status": status,
        "created_at": now_str,
    })

    if db is not None and database_schema is not None and hasattr(database_schema, "Song"):
        try:
            db_song = database_schema.Song(
                id=sid,
                title=title or "Untitled",
                prompt=prompt,
                lyrics=lyrics,
                genre=genre,
                mood=mood,
                audio_path=audio_path,
                image_path=image_path,
                is_liked=bool(is_liked),
                status=status,
                created_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(db_song)
            db.commit()
            if hasattr(db, "refresh"):
                try:
                    db.refresh(db_song)
                except Exception:
                    pass
            formatted = _format_song(db_song)
            _IN_MEMORY_SONGS[sid] = formatted
            return formatted
        except Exception:
            if hasattr(db, "rollback"):
                try:
                    db.rollback()
                except Exception:
                    pass

    _IN_MEMORY_SONGS[sid] = song_data
    return song_data


def get_song(song_id: str, db: Optional[Any] = None) -> Optional[SongData]:
    if not song_id:
        return None

    if db is not None and database_schema is not None and hasattr(database_schema, "Song"):
        try:
            song_obj = None
            if hasattr(db, "get"):
                song_obj = db.get(database_schema.Song, song_id)
            elif hasattr(db, "query"):
                song_obj = db.query(database_schema.Song).filter(database_schema.Song.id == song_id).first()
            if song_obj:
                formatted = _format_song(song_obj)
                _IN_MEMORY_SONGS[song_id] = formatted
                return formatted
        except Exception:
            pass

    return _IN_MEMORY_SONGS.get(song_id)


def list_songs(
    limit: int = 50,
    offset: int = 0,
    liked_only: bool = False,
    search: Optional[str] = None,
    db: Optional[Any] = None
) -> List[SongData]:
    results: List[SongData] = []

    if db is not None and database_schema is not None and hasattr(database_schema, "Song"):
        try:
            if hasattr(db, "query"):
                query = db.query(database_schema.Song)
                if liked_only:
                    query = query.filter(database_schema.Song.is_liked.is_(True))
                all_records = query.all()
                results = [_format_song(r) for r in all_records]
            elif hasattr(db, "exec"):
                from sqlmodel import select
                stmt = select(database_schema.Song)
                if liked_only:
                    stmt = stmt.where(database_schema.Song.is_liked == True)
                all_records = db.exec(stmt).all()
                results = [_format_song(r) for r in all_records]
            else:
                results = list(_IN_MEMORY_SONGS.values())
        except Exception:
            results = list(_IN_MEMORY_SONGS.values())
    else:
        results = list(_IN_MEMORY_SONGS.values())

    if liked_only:
        results = [s for s in results if s.get("is_liked")]

    if search:
        s_lower = search.lower()
        filtered = []
        for s in results:
            target = f"{s.get('title', '')} {s.get('prompt', '')} {s.get('lyrics', '')} {s.get('genre', '')} {s.get('mood', '')}".lower()
            if s_lower in target:
                filtered.append(s)
        results = filtered

    try:
        results.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    except Exception:
        pass

    start = max(0, offset)
    end = start + max(1, limit)
    return results[start:end]


def update_song(song_id: str, db: Optional[Any] = None, **kwargs) -> Optional[SongData]:
    song = get_song(song_id, db=db)
    if not song:
        return None

    if db is not None and database_schema is not None and hasattr(database_schema, "Song"):
        try:
            db_song = None
            if hasattr(db, "get"):
                db_song = db.get(database_schema.Song, song_id)
            elif hasattr(db, "query"):
                db_song = db.query(database_schema.Song).filter(database_schema.Song.id == song_id).first()

            if db_song:
                for k, v in kwargs.items():
                    if hasattr(db_song, k):
                        setattr(db_song, k, v)
                db.add(db_song)
                db.commit()
                if hasattr(db, "refresh"):
                    try:
                        db.refresh(db_song)
                    except Exception:
                        pass
                updated = _format_song(db_song)
                _IN_MEMORY_SONGS[song_id] = updated
                return updated
        except Exception:
            if hasattr(db, "rollback"):
                try:
                    db.rollback()
                except Exception:
                    pass

    for k, v in kwargs.items():
        song[k] = v
    _IN_MEMORY_SONGS[song_id] = song
    return song


def delete_song(song_id: str, db: Optional[Any] = None) -> bool:
    song = get_song(song_id, db=db)
    if not song and song_id not in _IN_MEMORY_SONGS:
        return False

    try:
        storage_manager.delete_song_files(song_id)
    except Exception:
        pass

    deleted_from_db = False
    if db is not None and database_schema is not None and hasattr(database_schema, "Song"):
        try:
            db_song = None
            if hasattr(db, "get"):
                db_song = db.get(database_schema.Song, song_id)
            elif hasattr(db, "query"):
                db_song = db.query(database_schema.Song).filter(database_schema.Song.id == song_id).first()

            if db_song:
                db.delete(db_song)
                db.commit()
                deleted_from_db = True
        except Exception:
            if hasattr(db, "rollback"):
                try:
                    db.rollback()
                except Exception:
                    pass

    if song_id in _IN_MEMORY_SONGS:
        del _IN_MEMORY_SONGS[song_id]
        return True

    return deleted_from_db


def toggle_like(song_id: str, db: Optional[Any] = None) -> Optional[SongData]:
    song = get_song(song_id, db=db)
    if not song:
        return None
    new_liked = not bool(song.get("is_liked", False))
    return update_song(song_id, db=db, is_liked=new_liked)


def get_quota(date_str: Optional[str] = None, max_quota: int = DEFAULT_MAX_QUOTA, db: Optional[Any] = None) -> QuotaData:
    d_str = date_str or _get_today_date_str()

    if db is not None and database_schema is not None and hasattr(database_schema, "UserQuota"):
        try:
            quota_obj = None
            if hasattr(db, "query"):
                quota_obj = db.query(database_schema.UserQuota).filter(database_schema.UserQuota.date == d_str).first()
            if quota_obj:
                count = getattr(quota_obj, "count", 0)
                m_quota = getattr(quota_obj, "max_quota", max_quota) or max_quota
                rem = max(0, m_quota - count)
                qd = QuotaData({
                    "id": getattr(quota_obj, "id", d_str),
                    "date": d_str,
                    "count": count,
                    "max_quota": m_quota,
                    "remaining": rem
                })
                _IN_MEMORY_QUOTAS[d_str] = qd
                return qd
        except Exception:
            pass

    if d_str not in _IN_MEMORY_QUOTAS:
        _IN_MEMORY_QUOTAS[d_str] = QuotaData({
            "id": d_str,
            "date": d_str,
            "count": 0,
            "max_quota": max_quota,
            "remaining": max_quota
        })

    q = _IN_MEMORY_QUOTAS[d_str]
    q["max_quota"] = max_quota
    q["remaining"] = max(0, max_quota - q["count"])
    return q


def check_quota(date_str: Optional[str] = None, max_quota: int = DEFAULT_MAX_QUOTA, db: Optional[Any] = None) -> bool:
    q = get_quota(date_str=date_str, max_quota=max_quota, db=db)
    return q["remaining"] > 0


def increment_quota(date_str: Optional[str] = None, max_quota: int = DEFAULT_MAX_QUOTA, db: Optional[Any] = None) -> QuotaData:
    d_str = date_str or _get_today_date_str()

    if db is not None and database_schema is not None and hasattr(database_schema, "UserQuota"):
        try:
            quota_obj = None
            if hasattr(db, "query"):
                quota_obj = db.query(database_schema.UserQuota).filter(database_schema.UserQuota.date == d_str).first()
            if not quota_obj:
                quota_obj = database_schema.UserQuota(id=str(uuid.uuid4()), date=d_str, count=1, max_quota=max_quota)
                db.add(quota_obj)
            else:
                quota_obj.count = getattr(quota_obj, "count", 0) + 1
            db.commit()
            if hasattr(db, "refresh"):
                try:
                    db.refresh(quota_obj)
                except Exception:
                    pass
            count = getattr(quota_obj, "count", 1)
            m_quota = getattr(quota_obj, "max_quota", max_quota) or max_quota
            rem = max(0, m_quota - count)
            qd = QuotaData({"id": getattr(quota_obj, "id", d_str), "date": d_str, "count": count, "max_quota": m_quota, "remaining": rem})
            _IN_MEMORY_QUOTAS[d_str] = qd
            return qd
        except Exception:
            if hasattr(db, "rollback"):
                try:
                    db.rollback()
                except Exception:
                    pass

    q = get_quota(date_str=d_str, max_quota=max_quota, db=None)
    new_count = q["count"] + 1
    new_quota = QuotaData({
        "id": q.get("id", d_str),
        "date": d_str,
        "count": new_count,
        "max_quota": max_quota,
        "remaining": max(0, max_quota - new_count)
    })
    _IN_MEMORY_QUOTAS[d_str] = new_quota
    return new_quota


def reset_quota(date_str: Optional[str] = None, max_quota: int = DEFAULT_MAX_QUOTA, db: Optional[Any] = None) -> QuotaData:
    d_str = date_str or _get_today_date_str()

    if db is not None and database_schema is not None and hasattr(database_schema, "UserQuota"):
        try:
            quota_obj = None
            if hasattr(db, "query"):
                quota_obj = db.query(database_schema.UserQuota).filter(database_schema.UserQuota.date == d_str).first()
            if quota_obj:
                quota_obj.count = 0
                db.add(quota_obj)
                db.commit()
        except Exception:
            if hasattr(db, "rollback"):
                try:
                    db.rollback()
                except Exception:
                    pass

    qd = QuotaData({
        "id": d_str,
        "date": d_str,
        "count": 0,
        "max_quota": max_quota,
        "remaining": max_quota
    })
    _IN_MEMORY_QUOTAS[d_str] = qd
    return qd


class SongsService:
    """
    Service class wrapping CRUD and quota operations.
    """
    def __init__(self, db=None, max_quota: int = DEFAULT_MAX_QUOTA):
        self.db = db
        self.max_quota = max_quota

    def create_song(self, title: str = "Untitled", prompt: str = "", lyrics: str = "",
                    genre: str = "", mood: str = "", song_id: Optional[str] = None,
                    status: str = "completed", audio_path: str = "", image_path: str = "",
                    is_liked: bool = False) -> SongData:
        return create_song(
            title=title, prompt=prompt, lyrics=lyrics, genre=genre, mood=mood,
            song_id=song_id, status=status, audio_path=audio_path, image_path=image_path,
            is_liked=is_liked, db=self.db
        )

    def get_song(self, song_id: str) -> Optional[SongData]:
        return get_song(song_id, db=self.db)

    def list_songs(self, limit: int = 50, offset: int = 0, liked_only: bool = False,
                   search: Optional[str] = None) -> List[SongData]:
        return list_songs(limit=limit, offset=offset, liked_only=liked_only, search=search, db=self.db)

    def update_song(self, song_id: str, **kwargs) -> Optional[SongData]:
        return update_song(song_id, db=self.db, **kwargs)

    def delete_song(self, song_id: str) -> bool:
        return delete_song(song_id, db=self.db)

    def toggle_like(self, song_id: str) -> Optional[SongData]:
        return toggle_like(song_id, db=self.db)

    def get_quota(self, date_str: Optional[str] = None) -> QuotaData:
        return get_quota(date_str=date_str, max_quota=self.max_quota, db=self.db)

    def check_quota(self, date_str: Optional[str] = None) -> bool:
        return check_quota(date_str=date_str, max_quota=self.max_quota, db=self.db)

    def increment_quota(self, date_str: Optional[str] = None) -> QuotaData:
        return increment_quota(date_str=date_str, max_quota=self.max_quota, db=self.db)

    def reset_quota(self, date_str: Optional[str] = None) -> QuotaData:
        return reset_quota(date_str=date_str, max_quota=self.max_quota, db=self.db)
