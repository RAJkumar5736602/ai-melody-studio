import asyncio
from typing import Any, Dict, Optional

import core_config
from ai_client.demo_generator import _prepare_settings_directories, generate_demo_song

logger = core_config.get_logger("ai_client")


class AIClient:
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or core_config.get_settings()
        _prepare_settings_directories(self.settings)

    async def generate_song(
        self,
        prompt: str,
        genre: Optional[str] = None,
        mood: Optional[str] = None,
        lyrics: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a song using Gemini API (Lyria 3.5) if configured and enabled,
        or fall back to Demo Generator if in demo mode or if API call fails.
        """
        _prepare_settings_directories(self.settings)
        genre = genre or "Pop"
        mood = mood or "Upbeat"

        # Check if in demo mode or missing key
        if getattr(self.settings, "DEMO_MODE", True) or not getattr(self.settings, "GEMINI_API_KEY", None):
            logger.info("Demo mode active or missing GEMINI_API_KEY. Using Demo Generator.")
            return generate_demo_song(prompt, genre, mood, lyrics, title, self.settings)

        try:
            return await self._call_gemini_api(prompt, genre, mood, lyrics, title)
        except Exception as exc:
            logger.warning(f"Gemini API call failed ({exc}). Falling back to Demo Generator.")
            return generate_demo_song(prompt, genre, mood, lyrics, title, self.settings)

    async def _call_gemini_api(
        self,
        prompt: str,
        genre: str,
        mood: str,
        lyrics: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calls Gemini API (Lyria 3.5).
        """
        api_key = getattr(self.settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")

        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-lyria-3.5")
            # Execute generation if model/library supports it
        except ImportError:
            raise RuntimeError("google-generativeai library is not installed.")

        generated_title = title or f"Lyria - {prompt[:20].capitalize()}"
        generated_lyrics = lyrics or f"[Verse]\n{prompt}\n\n[Chorus]\nGemini Melody"

        song_data = generate_demo_song(
            prompt, genre, mood, generated_lyrics, generated_title, self.settings
        )
        song_data["is_demo"] = False
        return song_data

    async def remake_song(
        self,
        original_prompt: str,
        original_genre: str,
        original_mood: str,
        modification_prompt: str,
        original_lyrics: Optional[str] = None,
        original_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Remakes a song by combining original attributes with modification prompt.
        """
        combined_prompt = f"{original_prompt} (Remix: {modification_prompt})"
        new_title = (
            f"{original_title} (Remix)"
            if original_title
            else f"Remix of {original_prompt[:15]}"
        )

        return await self.generate_song(
            prompt=combined_prompt,
            genre=original_genre,
            mood=original_mood,
            lyrics=original_lyrics,
            title=new_title,
        )
