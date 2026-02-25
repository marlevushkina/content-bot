"""Vault storage service for saving entries."""

from datetime import date, datetime
from pathlib import Path


class VaultStorage:
    """Service for storing entries in vault."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = Path(vault_path)
        self.daily_path = self.vault_path / "daily"

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.daily_path.mkdir(parents=True, exist_ok=True)

    def get_daily_file(self, day: date) -> Path:
        """Get path to daily file for given date."""
        self._ensure_dirs()
        return self.daily_path / f"{day.isoformat()}.md"

    def read_daily(self, day: date) -> str:
        """Read content of daily file."""
        file_path = self.get_daily_file(day)
        if not file_path.exists():
            return ""
        return file_path.read_text(encoding="utf-8")

    def append_to_daily(
        self,
        text: str,
        timestamp: datetime,
        msg_type: str,
    ) -> None:
        """Append entry to daily file.

        Args:
            text: Content to append
            timestamp: Entry timestamp
            msg_type: Type marker like [voice], [text]
        """
        self._ensure_dirs()
        file_path = self.get_daily_file(timestamp.date())

        time_str = timestamp.strftime("%H:%M")
        entry = f"\n## {time_str} {msg_type}\n{text}\n"

        with file_path.open("a", encoding="utf-8") as f:
            f.write(entry)
