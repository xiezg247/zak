"""回测页 A 股策略过滤：验证 reload 后仍能识别 Ashare* 策略。"""

from __future__ import annotations

import importlib
from glob import glob
from pathlib import Path

import vnpy_ctastrategy
from vnpy_ctastrategy import CtaTemplate, TargetPosTemplate

from vnpy_ashare.backtest_strategy_filter import filter_ashare_strategy_names


def _load_engine_classes(*, strategy_file_order: list[str] | None = None) -> dict[str, type]:
    """模拟 BacktesterEngine.load_strategy_class 的 import/reload 行为。"""
    classes: dict[str, type] = {}

    vnpy_path = Path(vnpy_ctastrategy.__file__).parent / "strategies"
    for filepath in glob(str(vnpy_path / "*.py")):
        name = f"vnpy_ctastrategy.strategies.{Path(filepath).stem}"
        module = importlib.import_module(name)
        importlib.reload(module)
        for attr in dir(module):
            value = getattr(module, attr)
            if isinstance(value, type) and issubclass(value, CtaTemplate) and value not in {CtaTemplate, TargetPosTemplate}:
                classes[value.__name__] = value

    project_path = Path.cwd() / "strategies"
    files = strategy_file_order or [Path(p).stem for p in glob(str(project_path / "*.py"))]
    for stem in files:
        name = f"strategies.{stem}"
        module = importlib.import_module(name)
        importlib.reload(module)
        for attr in dir(module):
            value = getattr(module, attr)
            if isinstance(value, type) and issubclass(value, CtaTemplate) and value not in {CtaTemplate, TargetPosTemplate}:
                classes[value.__name__] = value
    return classes


def test_ashare_strategy_names_after_reload() -> None:
    classes = _load_engine_classes()
    names = filter_ashare_strategy_names(classes)
    assert "AshareDoubleMaStrategy" in names
    assert "AtrRsiStrategy" not in names


def test_ashare_strategy_names_when_base_reloaded_last() -> None:
    """ashare_template 在 double_ma 之后 reload 时，issubclass 会失效，MRO 仍可用。"""
    classes = _load_engine_classes(
        strategy_file_order=["double_ma_strategy", "registry", "__init__", "ashare_template"],
    )
    names = filter_ashare_strategy_names(classes)
    assert names == ["AshareDoubleMaStrategy"]
