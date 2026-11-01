import os
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    """Application configuration container reading from environment variables."""

    APP_NAME: str = "AI Melody Studio"
    APP_VERSION: str = "1.0.0"

    GEMINI_API_KEY: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///./data/ai_melody_studio.db"
        )
    )
    LOG_LEVEL: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )

    AUDIO_DIR: Path = field(
        default_factory=lambda: Path(os.getenv("AUDIO_DIR", "./data/audio"))
    )
    IMAGE_DIR: Path = field(
        default_factory=lambda: Path(os.getenv("IMAGE_DIR", "./data/images"))
    )

    HOST: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = field(
        default_factory=lambda: int(os.getenv("PORT", "8000"))
    )

    MAX_DAILY_QUOTA: int = field(
        default_factory=lambda: int(os.getenv("MAX_DAILY_QUOTA", "10"))
    )

    _demo_mode_env: Optional[str] = field(
        default_factory=lambda: os.getenv("DEMO_MODE")
    )

    @property
    def DEMO_MODE(self) -> bool:
        """Demo mode is enabled explicitly via DEMO_MODE env var or fallback when GEMINI_API_KEY is missing."""
        if self._demo_mode_env is not None:
            return self._demo_mode_env.lower() in ("true", "1", "yes", "on")
        return not bool(self.GEMINI_API_KEY)

    def ensure_directories(self) -> None:
        """Create configured audio and image storage directories if they do not exist."""
        self.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        self.IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Instantiate and return a fresh Settings instance."""
    return Settings()


# Default module-level instance
settings = get_settings()


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """Configure system-wide logging format and level."""
    log_level_str = (level or settings.LOG_LEVEL).upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setLevel(log_level)

    logger = logging.getLogger("ai_melody_studio")
    logger.setLevel(log_level)
    return logger


def get_logger(name: str = "ai_melody_studio") -> logging.Logger:
    """Retrieve standard logger instance by name."""
    return logging.getLogger(name)
