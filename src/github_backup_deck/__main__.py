from __future__ import annotations

from github_backup_deck.cli import main

try:
    raise SystemExit(main())
except KeyboardInterrupt:
    raise SystemExit(130) from None
