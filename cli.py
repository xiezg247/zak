#!/usr/bin/env python3
"""zak 命令行入口（与 run.py 并列）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("ZAK_PROJECT_ROOT", str(_ROOT))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

from vnpy_ashare.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
