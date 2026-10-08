"""雷达跨页导航辅助。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.radar.navigation import (
    NavReject,
    require_host_method,
    sector_flow_call_kwargs,
)


class _Host:
    def open_sector_flow(self, *args, **kwargs) -> None:
        pass


def test_require_host_method() -> None:
    assert isinstance(
        require_host_method(None, "open_sector_flow", fail_message="无法打开"),
        NavReject,
    )
    assert require_host_method(_Host(), "open_sector_flow", fail_message="x") is None
    reject = require_host_method(_Host(), "missing", fail_message="无此方法")
    assert isinstance(reject, NavReject)
    assert reject.message == "无此方法"


def test_sector_flow_call_kwargs() -> None:
    assert sector_flow_call_kwargs([]) == {"sector_ids": None}
    assert sector_flow_call_kwargs(["银行"]) == {"sector_ids": ["银行"]}
    rot = sector_flow_call_kwargs(["银行"], rotation=True)
    assert rot == {
        "sector_ids": ["银行"],
        "tab": "rotation",
        "sector_kind": "industry",
    }
