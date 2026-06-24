"""板块资金监控控制器（组合各 mixin）。"""

from __future__ import annotations

from vnpy_ashare.ui.sector_flow.controller.ai_context import SectorFlowAiMixin
from vnpy_ashare.ui.sector_flow.controller.base import SectorFlowControllerBase
from vnpy_ashare.ui.sector_flow.controller.navigation import SectorFlowNavigationMixin
from vnpy_ashare.ui.sector_flow.controller.outlook import SectorFlowOutlookMixin
from vnpy_ashare.ui.sector_flow.controller.rotation import SectorFlowRotationMixin
from vnpy_ashare.ui.sector_flow.controller.snapshot import SectorFlowSnapshotMixin


class SectorFlowController(
    SectorFlowAiMixin,
    SectorFlowNavigationMixin,
    SectorFlowOutlookMixin,
    SectorFlowRotationMixin,
    SectorFlowSnapshotMixin,
    SectorFlowControllerBase,
):
    """板块资金页生命周期、快照刷新与各 Tab Worker 协调。"""
