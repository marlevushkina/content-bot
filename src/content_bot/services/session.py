"""Session persistence service.

Stores all bot interactions in JSONL format for history.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class SessionStore:
    """Persistent session storage in JSONL format."""

    def __init__(self, vault_path: Path | str) -> None:
        self.sessions_dir = Path(vault_path) / ".sessions"
        self.sessions_dir.mkdir(exist_ok=True)

    def _get_session_file(self, user_id: int) -> Path:
        return self.sessions_dir / f"{user_id}.jsonl"

    def append(self, user_id: int, entry_type: str, **data: Any) -> None:
        """Append entry to user's session file."""
        entry = {
            "ts": datetime.now().astimezone().isoformat(),
            "type": entry_type,
            **data,
        }
        path = self._get_session_file(user_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_recent(self, user_id: int, limit: int = 50) -> list[dict]:
        """Get recent session entries."""
        path = self._get_session_file(user_id)
        if not path.exists():
            return []

        entries = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return entries[-limit:]

    def get_today(self, user_id: int) -> list[dict]:
        """Get today's session entries."""
        today = datetime.now().date().isoformat()
        return [
            e
            for e in self.get_recent(user_id, limit=200)
            if e.get("ts", "").startswith(today)
        ]
