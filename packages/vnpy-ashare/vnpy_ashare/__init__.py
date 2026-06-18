"""VeighNa A 股行情应用（市场 / 自选 / 本地）。"""

import sys

from vnpy_common.paths import PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

__version__ = "0.1.0"
