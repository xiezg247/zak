"""Playbook 首屏对照条。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.trading.playbook import HomePlaybookStatus


class _HomeChip(QtWidgets.QFrame):
    """首页状态芯片：标签 + 主值 + 可选副文案。"""

    def __init__(self, label: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeChip")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        self._label = QtWidgets.QLabel(label)
        self._label.setObjectName("HomeChipLabel")
        self._value = QtWidgets.QLabel("—")
        self._value.setObjectName("HomeChipValue")
        self._value.setWordWrap(True)
        self._sub = QtWidgets.QLabel("")
        self._sub.setObjectName("HomeChipSub")
        self._sub.setWordWrap(True)

        layout.addWidget(self._label)
        layout.addWidget(self._value)
        layout.addWidget(self._sub)

    def set_content(self, value: str, *, sub: str = "", tone: str = "") -> None:
        self._value.setText(value)
        if sub:
            self._sub.setText(sub)
            self._sub.show()
        else:
            self._sub.clear()
            self._sub.hide()
        if tone:
            self.setProperty("tone", tone)
        else:
            self.setProperty("tone", "")
        self.style().unpolish(self)
        self.style().polish(self)


class HomePlaybookStatusStrip(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeStatusCard")
        self._emotion_loading = False

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        self._alert = QtWidgets.QLabel("")
        self._alert.setObjectName("HomeAlert")
        self._alert.setWordWrap(True)
        self._alert.hide()

        inner = QtWidgets.QFrame()
        inner.setObjectName("HomeStatusInner")
        row = QtWidgets.QHBoxLayout(inner)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(10)

        self._emotion = _HomeChip("情绪")
        self._risk = _HomeChip("风控")
        self._daily = _HomeChip("日盈亏")
        self._plan = _HomeChip("计划")
        self._position = _HomeChip("持仓")

        for chip in (self._emotion, self._risk, self._daily, self._plan, self._position):
            row.addWidget(chip, stretch=1)

        outer.addWidget(self._alert)
        outer.addWidget(inner)

    def set_emotion_loading(self, loading: bool) -> None:
        self._emotion_loading = loading
        if loading:
            self._emotion.set_content("加载中…", sub="")

    def apply(self, status: HomePlaybookStatus) -> None:
        if self._emotion_loading and status.emotion_label == "—":
            emotion_value = "加载中…"
            emotion_sub = ""
        elif status.emotion_label == "—":
            emotion_value = "暂无"
            emotion_sub = "可在市场页刷新"
        else:
            emotion_value = status.emotion_label
            emotion_sub = status.emotion_position_hint or ""

        daily_parts = status.daily_pnl_text.split(" / ", 1)
        daily_value = daily_parts[0]
        daily_sub = daily_parts[1] if len(daily_parts) > 1 else ""

        risk_sub = "可以新开仓" if status.allow_new_positions else "暂停新开仓"
        risk_tone = ""
        if not status.allow_new_positions:
            risk_tone = "danger"
        elif status.risk_label.startswith("警戒"):
            risk_tone = "caution"

        position_tone = "danger" if status.off_plan_symbols else ""

        self._emotion.set_content(emotion_value, sub=emotion_sub)
        self._risk.set_content(status.risk_label, sub=risk_sub, tone=risk_tone)
        self._daily.set_content(daily_value, sub=daily_sub)
        self._plan.set_content(status.plan_text)
        self._position.set_content(
            status.position_text,
            sub=status.discipline_progress,
            tone=position_tone,
        )

        if status.alert:
            self._alert.setText(status.alert)
            is_danger = status.risk_label.startswith("熔断") or bool(status.off_plan_symbols)
            self._alert.setProperty("severity", "danger" if is_danger else "info")
            self._alert.style().unpolish(self._alert)
            self._alert.style().polish(self._alert)
            self._alert.show()
        else:
            self._alert.hide()
            self._alert.setProperty("severity", "")
            self._alert.style().unpolish(self._alert)
            self._alert.style().polish(self._alert)
