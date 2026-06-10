"""A 股回测引擎：从项目根 strategies/ 加载策略（不依赖 cwd）。"""

from __future__ import annotations

from pathlib import Path

import vnpy_ctastrategy
from vnpy_ctabacktester.engine import BacktesterEngine

from vnpy_common.paths import PROJECT_ROOT

_PROJECT_STRATEGIES = PROJECT_ROOT / "strategies"
_PROJECT_STRATEGY_PRIORITY = ("ashare_template.py",)


class AshareBacktesterEngine(BacktesterEngine):
    """vnpy 回测引擎扩展：MainEngine 会 chdir 到 ~/.vntrader，需用绝对路径加载项目策略。"""

    def load_strategy_class(self) -> None:
        app_path = Path(vnpy_ctastrategy.__file__).parent
        self.load_strategy_class_from_folder(
            app_path.joinpath("strategies"),
            "vnpy_ctastrategy.strategies",
        )
        self._load_project_strategy_classes()

    def _load_project_strategy_classes(self) -> None:
        if not _PROJECT_STRATEGIES.is_dir():
            return

        loaded: set[str] = set()
        for filename in _PROJECT_STRATEGY_PRIORITY:
            path = _PROJECT_STRATEGIES / filename
            if not path.is_file():
                continue
            self.load_strategy_class_from_module(f"strategies.{path.stem}")
            loaded.add(path.stem)

        for path in sorted(_PROJECT_STRATEGIES.glob("*.py")):
            stem = path.stem
            if stem in loaded or stem == "__init__":
                continue
            self.load_strategy_class_from_module(f"strategies.{stem}")
