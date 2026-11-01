import contextlib
from datetime import datetime
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Generator

from core_config import get_settings, get_logger

logger = get_logger("database_schema")

HAS_SQLMODEL = False
HAS_SQLALCHEMY = False

try:
    from sqlmodel import SQLModel, Field, Session as SQLModelSession, create_engine as sqlmodel_create_engine
    HAS_SQLMODEL = True
except ImportError:
    try:
        import sqlalchemy
        from sqlalchemy import create_engine as sa_create_engine, Column, String, Integer, Boolean, DateTime, Text
        from sqlalchemy.orm import declarative_base, sessionmaker, Session as SASession
        HAS_SQLALCHEMY = True
    except ImportError:
        pass


def _extract_db_path(db_url: str) -> str:
    if db_url.startswith("sqlite:///"):
        path = db_url[10:]
        return path if path else ":memory:"
    if db_url == "sqlite://":
        return ":memory:"
    return db_url


if HAS_SQLMODEL:
    logger.info("Using SQLModel backend")

    class Song(SQLModel, table=True):
        __tablename__ = "songs"

        id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
        title: str
        prompt: str
        lyrics: Optional[str] = Field(default=None, nullable=True)
        genre: Optional[str] = Field(default=None, nullable=True)
        mood: Optional[str] = Field(default=None, nullable=True)
        audio_path: Optional[str] = Field(default=None, nullable=True)
        image_path: Optional[str] = Field(default=None, nullable=True)
        is_liked: bool = Field(default=False)
        status: str = Field(default="completed")
        created_at: datetime = Field(default_factory=datetime.utcnow)

        def dict(self, *args, **kwargs) -> Dict[str, Any]:
            return {
                "id": self.id,
                "title": self.title,
                "prompt": self.prompt,
                "lyrics": self.lyrics,
                "genre": self.genre,
                "mood": self.mood,
                "audio_path": self.audio_path,
                "image_path": self.image_path,
                "is_liked": bool(self.is_liked),
                "status": self.status,
                "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            }

    class UserQuota(SQLModel, table=True):
        __tablename__ = "user_quota"

        id: Optional[int] = Field(default=None, primary_key=True)
        date: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d"))
        count: int = Field(default=0)
        max_quota: int = Field(default=10)

        def dict(self, *args, **kwargs) -> Dict[str, Any]:
            return {
                "id": self.id,
                "date": self.date,
                "count": self.count,
                "max_quota": self.max_quota,
            }

    Session = SQLModelSession

    def get_engine(db_url: Optional[str] = None):
        if not db_url:
            db_url = get_settings().DATABASE_URL
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        return sqlmodel_create_engine(db_url, connect_args=connect_args)

    def create_db_and_tables(engine=None):
        if engine is None:
            engine = get_engine()
        SQLModel.metadata.create_all(engine)

    init_db = create_db_and_tables

    @contextlib.contextmanager
    def get_session(engine=None) -> Generator[SQLModelSession, None, None]:
        if engine is None:
            engine = get_engine()
        with SQLModelSession(engine) as session:
            yield session

elif HAS_SQLALCHEMY:
    logger.info("Using SQLAlchemy backend")
    Base = declarative_base()

    class Song(Base):
        __tablename__ = "songs"

        id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
        title = Column(String, nullable=False)
        prompt = Column(String, nullable=False)
        lyrics = Column(Text, nullable=True)
        genre = Column(String, nullable=True)
        mood = Column(String, nullable=True)
        audio_path = Column(String, nullable=True)
        image_path = Column(String, nullable=True)
        is_liked = Column(Boolean, default=False)
        status = Column(String, default="completed")
        created_at = Column(DateTime, default=datetime.utcnow)

        def __init__(self, **kwargs):
            if "id" not in kwargs or not kwargs["id"]:
                kwargs["id"] = str(uuid.uuid4())
            if "created_at" not in kwargs or not kwargs["created_at"]:
                kwargs["created_at"] = datetime.utcnow()
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self, *args, **kwargs) -> Dict[str, Any]:
            return {
                "id": self.id,
                "title": self.title,
                "prompt": self.prompt,
                "lyrics": self.lyrics,
                "genre": self.genre,
                "mood": self.mood,
                "audio_path": self.audio_path,
                "image_path": self.image_path,
                "is_liked": bool(self.is_liked),
                "status": self.status,
                "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            }

    class UserQuota(Base):
        __tablename__ = "user_quota"

        id = Column(Integer, primary_key=True, autoincrement=True)
        date = Column(String, nullable=False, default=lambda: datetime.utcnow().strftime("%Y-%m-%d"))
        count = Column(Integer, default=0)
        max_quota = Column(Integer, default=10)

        def __init__(self, **kwargs):
            if "date" not in kwargs or not kwargs["date"]:
                kwargs["date"] = datetime.utcnow().strftime("%Y-%m-%d")
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self, *args, **kwargs) -> Dict[str, Any]:
            return {
                "id": self.id,
                "date": self.date,
                "count": self.count,
                "max_quota": self.max_quota,
            }

    Session = SASession

    def get_engine(db_url: Optional[str] = None):
        if not db_url:
            db_url = get_settings().DATABASE_URL
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        return sa_create_engine(db_url, connect_args=connect_args)

    def create_db_and_tables(engine=None):
        if engine is None:
            engine = get_engine()
        Base.metadata.create_all(engine)

    init_db = create_db_and_tables

    @contextlib.contextmanager
    def get_session(engine=None) -> Generator[SASession, None, None]:
        if engine is None:
            engine = get_engine()
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

else:
    logger.info("Using standard library sqlite3 fallback backend")

    @dataclass
    class Song:
        title: str = ""
        prompt: str = ""
        lyrics: Optional[str] = None
        genre: Optional[str] = None
        mood: Optional[str] = None
        audio_path: Optional[str] = None
        image_path: Optional[str] = None
        is_liked: bool = False
        status: str = "completed"
        created_at: datetime = field(default_factory=datetime.utcnow)
        id: str = field(default_factory=lambda: str(uuid.uuid4()))

        def dict(self, *args, **kwargs) -> Dict[str, Any]:
            return {
                "id": self.id,
                "title": self.title,
                "prompt": self.prompt,
                "lyrics": self.lyrics,
                "genre": self.genre,
                "mood": self.mood,
                "audio_path": self.audio_path,
                "image_path": self.image_path,
                "is_liked": bool(self.is_liked),
                "status": self.status,
                "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            }

    @dataclass
    class UserQuota:
        id: Optional[int] = None
        date: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d"))
        count: int = 0
        max_quota: int = 10

        def dict(self, *args, **kwargs) -> Dict[str, Any]:
            return {
                "id": self.id,
                "date": self.date,
                "count": self.count,
                "max_quota": self.max_quota,
            }

    class QueryWrapper:
        def __init__(self, items: list):
            self._items = items

        def all(self) -> list:
            return list(self._items)

        def first(self) -> Optional[Any]:
            return self._items[0] if self._items else None

        def filter_by(self, **kwargs) -> "QueryWrapper":
            filtered = []
            for item in self._items:
                match = True
                for k, v in kwargs.items():
                    if getattr(item, k, None) != v:
                        match = False
                        break
                if match:
                    filtered.append(item)
            return QueryWrapper(filtered)

    class SQLiteEngine:
        def __init__(self, db_path: str):
            self.db_path = db_path
            self._shared_conn = None
            if db_path == ":memory:":
                self._shared_conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
                self._shared_conn.row_factory = sqlite3.Row

        def connect(self) -> sqlite3.Connection:
            if self._shared_conn:
                return self._shared_conn
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    class SQLiteSession:
        def __init__(self, engine: SQLiteEngine):
            self.engine = engine
            self.conn = engine.connect()
            self._pending_add = []
            self._pending_delete = []

        def add(self, instance: Any):
            if instance not in self._pending_add:
                self._pending_add.append(instance)

        def delete(self, instance: Any):
            if instance not in self._pending_delete:
                self._pending_delete.append(instance)

        def commit(self):
            cursor = self.conn.cursor()
            for obj in self._pending_add:
                if isinstance(obj, Song):
                    created_at_str = (
                        obj.created_at.isoformat()
                        if isinstance(obj.created_at, datetime)
                        else str(obj.created_at)
                    )
                    cursor.execute(
                        """
                        INSERT INTO songs (id, title, prompt, lyrics, genre, mood, audio_path, image_path, is_liked, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            title=excluded.title,
                            prompt=excluded.prompt,
                            lyrics=excluded.lyrics,
                            genre=excluded.genre,
                            mood=excluded.mood,
                            audio_path=excluded.audio_path,
                            image_path=excluded.image_path,
                            is_liked=excluded.is_liked,
                            status=excluded.status,
                            created_at=excluded.created_at
                        """,
                        (
                            obj.id,
                            obj.title,
                            obj.prompt,
                            obj.lyrics,
                            obj.genre,
                            obj.mood,
                            obj.audio_path,
                            obj.image_path,
                            1 if obj.is_liked else 0,
                            obj.status,
                            created_at_str,
                        ),
                    )
                elif isinstance(obj, UserQuota):
                    if obj.id is None:
                        cursor.execute(
                            "INSERT INTO user_quota (date, count, max_quota) VALUES (?, ?, ?)",
                            (obj.date, obj.count, obj.max_quota),
                        )
                        obj.id = cursor.lastrowid
                    else:
                        cursor.execute(
                            """
                            INSERT INTO user_quota (id, date, count, max_quota)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(id) DO UPDATE SET
                                date=excluded.date,
                                count=excluded.count,
                                max_quota=excluded.max_quota
                            """,
                            (obj.id, obj.date, obj.count, obj.max_quota),
                        )

            for obj in self._pending_delete:
                if isinstance(obj, Song):
                    cursor.execute("DELETE FROM songs WHERE id = ?", (obj.id,))
                elif isinstance(obj, UserQuota):
                    cursor.execute("DELETE FROM user_quota WHERE id = ?", (obj.id,))

            self.conn.commit()
            self._pending_add.clear()
            self._pending_delete.clear()

        def refresh(self, instance: Any):
            cursor = self.conn.cursor()
            if isinstance(instance, Song):
                cursor.execute("SELECT * FROM songs WHERE id = ?", (instance.id,))
                row = cursor.fetchone()
                if row:
                    instance.title = row["title"]
                    instance.prompt = row["prompt"]
                    instance.lyrics = row["lyrics"]
                    instance.genre = row["genre"]
                    instance.mood = row["mood"]
                    instance.audio_path = row["audio_path"]
                    instance.image_path = row["image_path"]
                    instance.is_liked = bool(row["is_liked"])
                    instance.status = row["status"]
                    if isinstance(row["created_at"], str):
                        try:
                            instance.created_at = datetime.fromisoformat(row["created_at"])
                        except Exception:
                            pass
            elif isinstance(instance, UserQuota):
                cursor.execute("SELECT * FROM user_quota WHERE id = ?", (instance.id,))
                row = cursor.fetchone()
                if row:
                    instance.date = row["date"]
                    instance.count = row["count"]
                    instance.max_quota = row["max_quota"]

        def get(self, model_cls: Any, pk: Any) -> Optional[Any]:
            cursor = self.conn.cursor()
            name = getattr(model_cls, "__name__", str(model_cls))
            if name == "Song" or model_cls is Song:
                cursor.execute("SELECT * FROM songs WHERE id = ?", (pk,))
                row = cursor.fetchone()
                if not row:
                    return None
                created_at = row["created_at"]
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except Exception:
                        pass
                return Song(
                    id=row["id"],
                    title=row["title"],
                    prompt=row["prompt"],
                    lyrics=row["lyrics"],
                    genre=row["genre"],
                    mood=row["mood"],
                    audio_path=row["audio_path"],
                    image_path=row["image_path"],
                    is_liked=bool(row["is_liked"]),
                    status=row["status"],
                    created_at=created_at,
                )
            elif name == "UserQuota" or model_cls is UserQuota:
                cursor.execute("SELECT * FROM user_quota WHERE id = ?", (pk,))
                row = cursor.fetchone()
                if not row:
                    return None
                return UserQuota(
                    id=row["id"],
                    date=row["date"],
                    count=row["count"],
                    max_quota=row["max_quota"],
                )
            return None

        def query(self, model_cls: Any) -> QueryWrapper:
            cursor = self.conn.cursor()
            name = getattr(model_cls, "__name__", str(model_cls))
            if name == "Song" or model_cls is Song:
                cursor.execute("SELECT * FROM songs ORDER BY created_at DESC")
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    created_at = row["created_at"]
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at)
                        except Exception:
                            pass
                    results.append(
                        Song(
                            id=row["id"],
                            title=row["title"],
                            prompt=row["prompt"],
                            lyrics=row["lyrics"],
                            genre=row["genre"],
                            mood=row["mood"],
                            audio_path=row["audio_path"],
                            image_path=row["image_path"],
                            is_liked=bool(row["is_liked"]),
                            status=row["status"],
                            created_at=created_at,
                        )
                    )
                return QueryWrapper(results)
            elif name == "UserQuota" or model_cls is UserQuota:
                cursor.execute("SELECT * FROM user_quota")
                rows = cursor.fetchall()
                results = [
                    UserQuota(
                        id=row["id"],
                        date=row["date"],
                        count=row["count"],
                        max_quota=row["max_quota"],
                    )
                    for row in rows
                ]
                return QueryWrapper(results)
            return QueryWrapper([])

        def exec(self, statement=None) -> QueryWrapper:
            return QueryWrapper([])

        def rollback(self):
            self.conn.rollback()
            self._pending_add.clear()
            self._pending_delete.clear()

        def close(self):
            if self.engine.db_path != ":memory:":
                self.conn.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                self.rollback()
            else:
                self.commit()
            self.close()

    Session = SQLiteSession

    def get_engine(db_url: Optional[str] = None) -> SQLiteEngine:
        if not db_url:
            db_url = get_settings().DATABASE_URL
        db_path = _extract_db_path(db_url)
        return SQLiteEngine(db_path)

    def create_db_and_tables(engine=None):
        if engine is None:
            engine = get_engine()
        conn = engine.connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS songs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                lyrics TEXT,
                genre TEXT,
                mood TEXT,
                audio_path TEXT,
                image_path TEXT,
                is_liked INTEGER DEFAULT 0,
                status TEXT DEFAULT 'completed',
                created_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_quota (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                max_quota INTEGER DEFAULT 10
            )
            """
        )
        conn.commit()

    init_db = create_db_and_tables

    @contextlib.contextmanager
    def get_session(engine=None) -> Generator[SQLiteSession, None, None]:
        if engine is None:
            engine = get_engine()
        session = SQLiteSession(engine)
        try:
            yield session
        finally:
            session.close()
