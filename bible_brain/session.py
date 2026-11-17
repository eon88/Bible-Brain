"""Local application preferences and use cases independent of the GUI."""

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .database import Database
from .datasets import BUNDLED_WEB, import_dataset, import_original_language

logger = logging.getLogger(__name__)
APPEARANCES = ("System", "Light", "Dark")
TEXT_SIZES = range(12, 31)


def default_data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "Bible Brain" if local else Path.home() / ".bible-brain"


@dataclass(frozen=True)
class Preferences:
    database_path: str
    appearance: str = "System"
    text_size: int = 19

    @classmethod
    def from_file(cls, path: Path, default_database: Path) -> "Preferences":
        if not path.exists():
            return cls(str(default_database))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Settings must contain a JSON object.")
            database = data.get("database_path", str(default_database))
            if not isinstance(database, str) or not Path(database).is_absolute():
                raise ValueError("The database path must be absolute.")
            appearance, text_size = _validate_appearance(
                data.get("appearance", "System"), data.get("text_size", 19),
            )
        except (ValueError, UnicodeError) as error:
            raise ValueError(f"Settings could not be read from {path}. {error}") from error
        return cls(database, appearance, text_size)


def _validate_appearance(appearance: str, text_size: int) -> tuple[str, int]:
    if appearance not in APPEARANCES:
        raise ValueError("Choose System, Light or Dark appearance.")
    if type(text_size) is not int or text_size not in TEXT_SIZES:
        raise ValueError("Choose a reader text size between 12 and 30.")
    return appearance, text_size


class Session:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.data_dir / "settings.json"
        default_database = self.data_dir / "library.sqlite3"
        self._preferences = Preferences.from_file(self.settings_path, default_database)
        if self.database_path != default_database and not self.database_path.is_file():
            raise ValueError(f"Reconnect the drive or put the configured database back at {self.database_path}.")
        self.database = self._open_database(self.database_path)

    @property
    def database_path(self) -> Path:
        return Path(self._preferences.database_path)

    @property
    def appearance(self) -> str:
        return self._preferences.appearance

    @property
    def text_size(self) -> int:
        return self._preferences.text_size

    @staticmethod
    def _open_database(path: Path) -> Database:
        database = Database(path)
        try:
            if not database.translations():
                count = import_dataset(database, BUNDLED_WEB)
                logger.info("Installed bundled Scripture (%d addresses)", count)
            return database
        except Exception:
            database.close()
            raise

    def _save(self, preferences: Preferences) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.data_dir, prefix="settings-", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(asdict(preferences), stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.settings_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self._preferences = preferences

    def set_appearance(self, appearance: str, text_size: int) -> None:
        appearance, text_size = _validate_appearance(appearance, text_size)
        self._save(replace(self._preferences, appearance=appearance, text_size=text_size))

    def _database_file(self, path: Path) -> Path:
        path = Path(path).expanduser().resolve()
        reserved = (
            self.settings_path, self.data_dir / "bible-brain.log", self.data_dir / "application.lock",
        )
        if path in reserved:
            raise ValueError("Choose a path separate from the application settings and logs.")
        return path

    def switch_database(self, path: Path) -> None:
        path = self._database_file(path)
        if path == self.database_path:
            return
        candidate = self._open_database(path)
        try:
            self._save(replace(self._preferences, database_path=str(path)))
        except Exception:
            candidate.close()
            raise
        previous = self.database
        self.database = candidate
        previous.close()
        logger.info("Opened a different local Bible Brain database")

    def import_dataset(self, path: Path) -> int:
        count = import_dataset(self.database, path)
        logger.info("Translation import completed (%d new addresses)", count)
        return count

    def import_original_language(self, path: Path) -> int:
        count = import_original_language(self.database, path)
        logger.info("Original-language import completed (%d tokens)", count)
        return count

    def backup(self, path: Path) -> None:
        self.database.backup_to(self._database_file(path))
        logger.info("Database backup completed")

    def restore(self, path: Path) -> Path:
        previous = self.database.restore_from(self._database_file(path))
        logger.info("Database restore completed")
        return previous

    def close(self) -> None:
        self.database.close()
