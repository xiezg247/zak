"""板块未来展望 C（LLM）后台生成。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy.trader.ui import QtCore

from vnpy_ashare.domain.market.sector_flow import SectorFlowOutlookBundle
from vnpy_ashare.services.sector_flow_outlook_llm import generate_llm_outlook

if TYPE_CHECKING:
    from vnpy_llm.config.settings import LlmConfig


class SectorFlowOutlookLlmWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        bundle: SectorFlowOutlookBundle,
        config: LlmConfig | Any,
        *,
        strategy_class: str | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bundle = bundle
        self._config = config
        self._strategy_class = strategy_class
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        try:
            llm = generate_llm_outlook(
                self._bundle,
                self._config,
                strategy_class=self._strategy_class,
            )
        except Exception as ex:
            if not self._cancelled:
                self.failed.emit(str(ex))
            return
        if self._cancelled:
            return
        updated = self._bundle.model_copy(update={"llm": llm})
        self.finished.emit(updated)
