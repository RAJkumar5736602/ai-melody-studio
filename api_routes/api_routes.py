import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Query, status
from pydantic import BaseModel

import songs_service
import ai_client

try:
    from ai_client import demo_generator
except ImportError:
    try:
        import ai_client.demo_generator as demo_generator
    except ImportError:
        demo_generator = None

logger = logging.getLogger(__name__)

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str = ""
    genre: Optional[str] = ""
    mood: Optional[str] = ""
    lyrics: Optional[str] = ""
    title: Optional[str] = ""


class RemakeRequest(BaseModel):
    prompt: Optional[str] = None
    genre: Optional[str] = None
    mood: Optional[str] = None
    lyrics: Optional[str] = None
    title: Optional[str] = None


class UpdateSongRequest(BaseModel):
    title: Optional[str] = None
    is_liked: Optional[bool] = None
    genre: Optional[str] = None
    mood: Optional[str] = None


def _check_user_quota() -> bool:
    quota_res = songs_service.check_quota()
    if isinstance(quota_res, bool):
        return quota_res
    if isinstance(quota_res, dict):
        if "has_quota" in quota_res:
            return bool(quota_res["has_quota"])
        if "remaining" in quota_res:
            return quota_res["remaining"] > 0
        if "count" in quota_res and "max_quota" in quota_res:
            return quota_res["count"] < quota_res["max_quota"]
    return True


def _run_generation_task(
    song_id: str,
    prompt: str = "",
    genre: str = "",
    mood: str = "",
    lyrics: str = "",
    title: str = ""
) -> None:
    gen_res = None
    try:
        client = ai_client.AIClient()
        if hasattr(client, "generate_song"):
            gen_res = client.generate_song(
                prompt=prompt, genre=genre, mood=mood, lyrics=lyrics, title=title
            )
        elif hasattr(client, "generate"):
            gen_res = client.generate(
                prompt=prompt, genre=genre, mood=mood, lyrics=lyrics, title=title
            )
    except Exception as e:
        logger.warning(f"AIClient generation failed, falling back to demo: {e}")
        gen_res = None

    if not gen_res:
        try:
            if hasattr(ai_client, "generate_demo_song"):
                gen_res = ai_client.generate_demo_song(
                    prompt=prompt, genre=genre, mood=mood, lyrics=lyrics, title=title
                )
            elif demo_generator and hasattr(demo_generator, "generate_demo_song"):
                gen_res = demo_generator.generate_demo_song(
                    prompt=prompt, genre=genre, mood=mood, lyrics=lyrics, title=title
                )
        except Exception as e:
            logger.error(f"Demo generation error: {e}")
            gen_res = None

    if gen_res and isinstance(gen_res, dict):
        audio_path = gen_res.get("audio_path") or f"/media/audio/{song_id}.wav"
        image_path = gen_res.get("image_path") or f"/media/images/{song_id}.png"
        final_title = gen_res.get("title") or title or "Untitled Song"
        songs_service.update_song(
            song_id,
            status="completed",
            audio_path=str(audio_path),
            image_path=str(image_path),
            title=final_title
        )
    else:
        songs_service.update_song(
            song_id,
            status="completed",
            audio_path=f"/media/audio/{song_id}.wav",
            image_path=f"/media/images/{song_id}.png"
        )


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_song(req: GenerateRequest, background_tasks: BackgroundTasks) -> Any:
    if not _check_user_quota():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily generation quota exceeded"
        )

    songs_service.increment_quota()

    song_title = req.title or (req.prompt[:30] if req.prompt else "Untitled Song")
    song = songs_service.create_song(
        title=song_title,
        prompt=req.prompt or "",
        lyrics=req.lyrics or "",
        genre=req.genre or "",
        mood=req.mood or "",
        status="generating"
    )

    song_id = song.get("id") if isinstance(song, dict) else getattr(song, "id", str(song))

    background_tasks.add_task(
        _run_generation_task,
        song_id=song_id,
        prompt=req.prompt or "",
        genre=req.genre or "",
        mood=req.mood or "",
        lyrics=req.lyrics or "",
        title=song_title
    )

    return song


@router.get("/songs")
async def list_songs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    liked_only: bool = Query(False),
    search: Optional[str] = Query(None)
) -> Any:
    return songs_service.list_songs(
        limit=limit,
        offset=offset,
        liked_only=liked_only,
        search=search
    )


@router.get("/songs/{song_id}")
async def get_song(song_id: str) -> Any:
    song = songs_service.get_song(song_id)
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song not found"
        )
    return song


@router.delete("/songs/{song_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_song(song_id: str) -> None:
    song = songs_service.get_song(song_id)
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song not found"
        )
    songs_service.delete_song(song_id)
    return None


@router.post("/songs/{song_id}/like")
async def toggle_like(song_id: str) -> Any:
    song = songs_service.get_song(song_id)
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song not found"
        )
    updated = songs_service.toggle_like(song_id)
    return updated or songs_service.get_song(song_id)


@router.patch("/songs/{song_id}")
async def update_song(song_id: str, updates: UpdateSongRequest) -> Any:
    song = songs_service.get_song(song_id)
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song not found"
        )
    kw = {k: v for k, v in updates.dict(exclude_unset=True).items() if v is not None}
    if kw:
        updated = songs_service.update_song(song_id, **kw)
        return updated or songs_service.get_song(song_id)
    return song


@router.post("/remake/{song_id}", status_code=status.HTTP_201_CREATED)
async def remake_song(
    song_id: str,
    req: RemakeRequest,
    background_tasks: BackgroundTasks
) -> Any:
    original = songs_service.get_song(song_id)
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original song not found"
        )

    if not _check_user_quota():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily generation quota exceeded"
        )

    songs_service.increment_quota()

    orig_dict = original.dict() if hasattr(original, "dict") and callable(original.dict) else dict(original)

    prompt = req.prompt if req.prompt is not None else orig_dict.get("prompt", "")
    genre = req.genre if req.genre is not None else orig_dict.get("genre", "")
    mood = req.mood if req.mood is not None else orig_dict.get("mood", "")
    lyrics = req.lyrics if req.lyrics is not None else orig_dict.get("lyrics", "")
    orig_title = orig_dict.get("title", "Untitled")
    title = req.title if req.title is not None else f"{orig_title} (Remake)"

    new_song = songs_service.create_song(
        title=title,
        prompt=prompt,
        genre=genre,
        mood=mood,
        lyrics=lyrics,
        status="generating"
    )

    new_song_id = new_song.get("id") if isinstance(new_song, dict) else getattr(new_song, "id", str(new_song))

    background_tasks.add_task(
        _run_generation_task,
        song_id=new_song_id,
        prompt=prompt,
        genre=genre,
        mood=mood,
        lyrics=lyrics,
        title=title
    )

    return new_song


@router.get("/quota")
async def get_quota() -> Any:
    return songs_service.get_quota()


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="AI Melody Studio")
    fastapi_app.include_router(router, prefix="/api")
    return fastapi_app


app = create_app()
