from __future__ import annotations

import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

os.environ.setdefault("SENTINEL_AUTH_DISABLED", "true")

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
