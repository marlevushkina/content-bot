"""Git automation service for vault."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class VaultGit:
    """Service for git operations on vault."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = Path(vault_path)

    def _run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run git command in vault directory."""
        return subprocess.run(
            ["git", *args],
            cwd=self.vault_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        result = self._run_git("status", "--porcelain")
        return bool(result.stdout.strip())

    def commit_changes(self, message: str) -> bool:
        """Stage all changes and commit."""
        if not self.has_changes():
            logger.info("No changes to commit")
            return False

        add_result = self._run_git("add", "-A")
        if add_result.returncode != 0:
            logger.error("Git add failed: %s", add_result.stderr)
            return False

        commit_result = self._run_git("commit", "-m", message)
        if commit_result.returncode != 0:
            logger.error("Git commit failed: %s", commit_result.stderr)
            return False

        logger.info("Committed: %s", message)
        return True

    def push(self) -> bool:
        """Push to remote."""
        result = self._run_git("push")
        if result.returncode != 0:
            logger.error("Git push failed: %s", result.stderr)
            return False

        logger.info("Pushed to remote")
        return True

    def commit_and_push(self, message: str) -> bool:
        """Commit all changes and push."""
        if self.commit_changes(message):
            return self.push()
        return True
