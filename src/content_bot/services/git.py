"""Git operations for vault."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class VaultGit:
    """Simple git operations on the vault repository.

    Auto-commit only fires when the vault sits inside a git repo; otherwise the
    git calls fail and are caught — the bot keeps working without version control.
    """

    def __init__(self, vault_path: Path) -> None:
        vault_path = Path(vault_path).resolve()
        # Git repo is the parent of the vault dir; scope commits to <vault>/content
        # so unrelated edits in the repo are never swept into a content commit.
        self.repo_path = vault_path.parent
        self.scope = f"{vault_path.name}/content"

    def commit_and_push(self, message: str) -> bool:
        """Stage content changes in the vault, commit and push."""
        try:
            subprocess.run(
                ["git", "add", self.scope],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )

            # Check if there's anything to commit
            result = subprocess.run(
                ["git", "status", "--porcelain", self.scope],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            if not result.stdout.strip():
                logger.info("No changes to commit")
                return False

            subprocess.run(
                ["git", "commit", "-m", message, "--", self.scope],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "push"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            logger.info("Committed and pushed: %s", message)
            return True
        except subprocess.CalledProcessError as e:
            logger.warning("Git operation failed: %s", e.stderr if e.stderr else e)
            return False
