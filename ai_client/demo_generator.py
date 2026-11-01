import math
import struct
import uuid
import wave
from pathlib import Path
from typing import Any, Dict, Optional

import core_config


def _prepare_settings_directories(settings: Any) -> Any:
    if settings is None:
        settings = core_config.get_settings()

    if hasattr(settings, "AUDIO_DIR") and isinstance(settings.AUDIO_DIR, str):
        settings.AUDIO_DIR = Path(settings.AUDIO_DIR)
    if hasattr(settings, "IMAGE_DIR") and isinstance(settings.IMAGE_DIR, str):
        settings.IMAGE_DIR = Path(settings.IMAGE_DIR)

    if hasattr(settings, "ensure_directories") and callable(settings.ensure_directories):
        try:
            settings.ensure_directories()
        except Exception:
            pass

    if hasattr(settings, "AUDIO_DIR") and settings.AUDIO_DIR:
        Path(settings.AUDIO_DIR).mkdir(parents=True, exist_ok=True)
    if hasattr(settings, "IMAGE_DIR") and settings.IMAGE_DIR:
        Path(settings.IMAGE_DIR).mkdir(parents=True, exist_ok=True)

    return settings


def generate_demo_wav(file_path: Path, duration_sec: float = 2.0, sample_rate: int = 22050) -> None:
    num_samples = int(duration_sec * sample_rate)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(file_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for i in range(num_samples):
            t = float(i) / sample_rate
            freq = 261.63 if (t % 1.0) < 0.33 else (329.63 if (t % 1.0) < 0.66 else 392.00)
            val = int(16384.0 * math.sin(2.0 * math.pi * freq * t))
            data = struct.pack("<h", val)
            wav_file.writeframesraw(data)


def generate_demo_image(file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (300, 300), color=(50, 70, 100))
        d = ImageDraw.Draw(img)
        d.text((20, 20), "AI Melody Studio Demo", fill=(255, 255, 255))
        img.save(file_path, "PNG")
    except Exception:
        import zlib

        width, height = 100, 100
        raw_data = bytes([0] + [50, 80, 120] * width) * height
        compressed = zlib.compress(raw_data)

        def chunk(chunk_type: bytes, data: bytes) -> bytes:
            return (
                len(data).to_bytes(4, "big")
                + chunk_type
                + data
                + zlib.crc32(chunk_type + data).to_bytes(4, "big")
            )

        header = b"\x89PNG\r\n\x1a\n"
        ihdr = chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 2, 0, 0, 0]))
        idat = chunk(b"IDAT", compressed)
        iend = chunk(b"IEND", b"")
        file_path.write_bytes(header + ihdr + idat + iend)


def generate_demo_song(
    prompt: str,
    genre: Optional[str] = None,
    mood: Optional[str] = None,
    lyrics: Optional[str] = None,
    title: Optional[str] = None,
    settings: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Generates demo audio and image files locally when running in Demo Mode
    or as a fallback when API calls fail.
    """
    settings = _prepare_settings_directories(settings)

    song_id = str(uuid.uuid4())[:8]
    genre = genre or "Pop"
    mood = mood or "Upbeat"

    if not title:
        words = prompt.strip().split()
        short_prompt = " ".join(words[:4]).capitalize() if words else "Melody"
        title = f"Demo - {short_prompt}"

    if not lyrics:
        lyrics = (
            f"[Verse 1]\n"
            f"Walking through the soundscapes, feeling {mood.lower()}.\n"
            f"Notes are drifting softly, playing {genre.lower()} in the night.\n\n"
            f"[Chorus]\n"
            f"{prompt}\n"
            f"This is our AI melody, shine so bright.\n\n"
            f"[Outro]\n"
            f"Fading out..."
        )

    audio_filename = f"demo_{song_id}.wav"
    image_filename = f"demo_{song_id}.png"

    audio_path = Path(settings.AUDIO_DIR) / audio_filename
    image_path = Path(settings.IMAGE_DIR) / image_filename

    generate_demo_wav(audio_path)
    generate_demo_image(image_path)

    return {
        "title": title,
        "prompt": prompt,
        "lyrics": lyrics,
        "genre": genre,
        "mood": mood,
        "audio_path": str(audio_path),
        "image_path": str(image_path),
        "is_demo": True,
    }
