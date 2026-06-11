"""Process-wide locks to serialize vault writes and git operations.

The bot runs as a single process; these locks prevent two long generations
(or their git commits) from racing on the same files in the shared vault.
"""

import asyncio

# Held around generation + file write + commit for /content, /plan, reconcile,
# and around standalone commits (notes, ideas, publish marks).
vault_lock = asyncio.Lock()
