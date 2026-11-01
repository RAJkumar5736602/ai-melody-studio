from pathlib import Path
from typing import Optional, Dict, Union
import core_config

logger = core_config.get_logger("storage_manager")


class StorageManager:
    """Handles local file system IO for audio and image assets."""

    def __init__(
        self,
        settings=None,
        audio_dir: Optional[Union[str, Path]] = None,
        image_dir: Optional[Union[str, Path]] = None,
    ):
        if settings is None:
            settings = core_config.get_settings()
        self.settings = settings

        if hasattr(self.settings, "ensure_directories") and callable(
            self.settings.ensure_directories
        ):
            self.settings.ensure_directories()

        if audio_dir is not None:
            self.audio_dir = Path(audio_dir)
        else:
            self.audio_dir = Path(getattr(self.settings, "AUDIO_DIR", "data/audio"))

        if image_dir is not None:
            self.image_dir = Path(image_dir)
        else:
            self.image_dir = Path(getattr(self.settings, "IMAGE_DIR", "data/images"))

        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, filename_or_id: str) -> str:
        if not filename_or_id or not isinstance(filename_or_id, str):
            raise ValueError("Filename or song ID must be a non-empty string.")
        clean = Path(filename_or_id).name
        if not clean or clean in (".", ".."):
            raise ValueError(f"Invalid filename or ID: '{filename_or_id}'")
        return clean

    def _resolve_path(
        self, base_dir: Path, filename_or_id: str, default_ext: str
    ) -> Path:
        clean = self._sanitize_name(filename_or_id)
        base_resolved = base_dir.resolve()

        direct_path = base_dir / clean
        if direct_path.is_file():
            try:
                direct_path.resolve().relative_to(base_resolved)
                return direct_path
            except ValueError:
                raise ValueError(f"Path traversal detected: '{filename_or_id}'")

        if not Path(clean).suffix:
            matches = [f for f in base_dir.glob(f"{clean}.*") if f.is_file()]
            if matches:
                return matches[0]
            ext = default_ext.lstrip(".")
            target = base_dir / f"{clean}.{ext}"
        else:
            target = direct_path

        try:
            target.resolve().relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"Path traversal detected: '{filename_or_id}'")

        return target

    def save_audio(self, data: bytes, song_id: str, extension: str = "mp3") -> str:
        clean_id = self._sanitize_name(song_id)
        ext = extension.lstrip(".")

        if Path(clean_id).suffix:
            filename = clean_id
        else:
            filename = f"{clean_id}.{ext}"

        file_path = self.audio_dir / filename
        try:
            file_path.resolve().relative_to(self.audio_dir.resolve())
        except ValueError:
            raise ValueError(f"Path traversal detected in song_id: '{song_id}'")

        file_path.write_bytes(data)
        logger.info("Saved audio file: %s (%d bytes)", file_path, len(data))
        return str(file_path)

    def save_image(self, data: bytes, song_id: str, extension: str = "png") -> str:
        clean_id = self._sanitize_name(song_id)
        ext = extension.lstrip(".")

        if Path(clean_id).suffix:
            filename = clean_id
        else:
            filename = f"{clean_id}.{ext}"

        file_path = self.image_dir / filename
        try:
            file_path.resolve().relative_to(self.image_dir.resolve())
        except ValueError:
            raise ValueError(f"Path traversal detected in song_id: '{song_id}'")

        file_path.write_bytes(data)
        logger.info("Saved image file: %s (%d bytes)", file_path, len(data))
        return str(file_path)

    def get_audio_path(self, filename_or_id: str) -> Path:
        return self._resolve_path(self.audio_dir, filename_or_id, "mp3")

    def get_image_path(self, filename_or_id: str) -> Path:
        return self._resolve_path(self.image_dir, filename_or_id, "png")

    def audio_exists(self, filename_or_id: str) -> bool:
        try:
            path = self.get_audio_path(filename_or_id)
            return path.is_file()
        except ValueError:
            return False

    def image_exists(self, filename_or_id: str) -> bool:
        try:
            path = self.get_image_path(filename_or_id)
            return path.is_file()
        except ValueError:
            return False

    def read_audio(self, filename_or_id: str) -> bytes:
        path = self.get_audio_path(filename_or_id)
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: '{filename_or_id}'")
        return path.read_bytes()

    def read_image(self, filename_or_id: str) -> bytes:
        path = self.get_image_path(filename_or_id)
        if not path.is_file():
            raise FileNotFoundError(f"Image file not found: '{filename_or_id}'")
        return path.read_bytes()

    def delete_audio(self, filename_or_id: str) -> bool:
        clean = self._sanitize_name(filename_or_id)
        deleted = False

        if Path(clean).suffix:
            direct_path = self.audio_dir / clean
            if direct_path.is_file():
                direct_path.unlink()
                deleted = True
        else:
            matches = [f for f in self.audio_dir.glob(f"{clean}.*") if f.is_file()]
            for match in matches:
                match.unlink()
                deleted = True

        if deleted:
            logger.info("Deleted audio file(s) for: %s", filename_or_id)
        return deleted

    def delete_image(self, filename_or_id: str) -> bool:
        clean = self._sanitize_name(filename_or_id)
        deleted = False

        if Path(clean).suffix:
            direct_path = self.image_dir / clean
            if direct_path.is_file():
                direct_path.unlink()
                deleted = True
        else:
            matches = [f for f in self.image_dir.glob(f"{clean}.*") if f.is_file()]
            for match in matches:
                match.unlink()
                deleted = True

        if deleted:
            logger.info("Deleted image file(s) for: %s", filename_or_id)
        return deleted

    def delete_song_files(self, song_id: str) -> Dict[str, bool]:
        audio_deleted = self.delete_audio(song_id)
        image_deleted = self.delete_image(song_id)
        return {"audio": audio_deleted, "image": image_deleted}


_default_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    global _default_storage_manager
    if _default_storage_manager is None:
        _default_storage_manager = StorageManager()
    return _default_storage_manager


def save_audio(data: bytes, song_id: str, extension: str = "mp3") -> str:
    return get_storage_manager().save_audio(data, song_id, extension)


def save_image(data: bytes, song_id: str, extension: str = "png") -> str:
    return get_storage_manager().save_image(data, song_id, extension)


def get_audio_path(filename_or_id: str) -> Path:
    return get_storage_manager().get_audio_path(filename_or_id)


def get_image_path(filename_or_id: str) -> Path:
    return get_storage_manager().get_image_path(filename_or_id)


def read_audio(filename_or_id: str) -> bytes:
    return get_storage_manager().read_audio(filename_or_id)


def read_image(filename_or_id: str) -> bytes:
    return get_storage_manager().read_image(filename_or_id)


def delete_audio(filename_or_id: str) -> bool:
    return get_storage_manager().delete_audio(filename_or_id)


def delete_image(filename_or_id: str) -> bool:
    return get_storage_manager().delete_image(filename_or_id)


def delete_song_files(song_id: str) -> Dict[str, bool]:
    return get_storage_manager().delete_song_files(song_id)


def audio_exists(filename_or_id: str) -> bool:
    return get_storage_manager().audio_exists(filename_or_id)


def image_exists(filename_or_id: str) -> bool:
    return get_storage_manager().image_exists(filename_or_id)
