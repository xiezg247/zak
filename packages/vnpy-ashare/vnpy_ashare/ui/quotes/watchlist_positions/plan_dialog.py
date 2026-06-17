"""今日交易计划对话框。"""

from __future__ import annotations

from datetime import datetime

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.market_hours import CHINA_TZ
from vnpy_ashare.domain.trading_plan import TradingPlanRecord
from vnpy_ashare.storage.repositories.trading_plans import (
    activate_trading_plan,
    create_trading_plan,
    load_active_trading_plan,
    replace_trading_plan_symbols,
    update_trading_plan_meta,
)
from vnpy_ashare.trading.journal.propose import (
    build_trading_plan_draft,
    sync_plan_to_observation_group,
)
from vnpy_ashare.trading.journal.propose import _next_trade_date


class TradingPlanDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        page,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent or page)
        self._page = page
        self._plan_id: str | None = None
        self.setWindowTitle("今日交易计划")
        self.setMinimumWidth(420)

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self._date_edit = QtWidgets.QDateEdit(self)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        today = datetime.now(CHINA_TZ).date()
        self._date_edit.setDate(QtCore.QDate(today.year, today.month, today.day))
        form.addRow("计划日", self._date_edit)

        self._max_pct_spin = QtWidgets.QDoubleSpinBox(self)
        self._max_pct_spin.setRange(0, 80)
        self._max_pct_spin.setSuffix(" %")
        self._max_pct_spin.setDecimals(0)
        form.addRow("计划总仓位", self._max_pct_spin)

        self._emotion_label = QtWidgets.QLabel("—", self)
        form.addRow("预期情绪", self._emotion_label)

        self._symbols_edit = QtWidgets.QPlainTextEdit(self)
        self._symbols_edit.setPlaceholderText("每行一个 vt_symbol，如 600519.SSE（最多 5 只）")
        self._symbols_edit.setMaximumHeight(120)
        form.addRow("观察名单", self._symbols_edit)

        self._notes_edit = QtWidgets.QPlainTextEdit(self)
        self._notes_edit.setMaximumHeight(72)
        form.addRow("备忘", self._notes_edit)

        self._status_label = QtWidgets.QLabel("", self)
        self._status_label.setObjectName("SettingsHint")
        form.addRow("状态", self._status_label)

        layout.addLayout(form)

        buttons = QtWidgets.QHBoxLayout()
        self._draft_button = QtWidgets.QPushButton("生成草案", self)
        self._save_button = QtWidgets.QPushButton("保存", self)
        self._activate_button = QtWidgets.QPushButton("激活", self)
        self._sync_button = QtWidgets.QPushButton("同步观察组", self)
        close_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.addWidget(self._draft_button)
        buttons.addWidget(self._save_button)
        buttons.addWidget(self._activate_button)
        buttons.addWidget(self._sync_button)
        buttons.addStretch(1)
        buttons.addWidget(close_box)
        layout.addLayout(buttons)

        self._draft_button.clicked.connect(self._on_generate_draft)
        self._save_button.clicked.connect(self._on_save)
        self._activate_button.clicked.connect(self._on_activate)
        self._sync_button.clicked.connect(self._on_sync_group)
        close_box.rejected.connect(self.reject)

        self._load_active_plan()

    def _trade_date(self) -> str:
        qdate = self._date_edit.date()
        return f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"

    def _parse_symbols(self) -> list[tuple[str, Exchange]]:
        from vnpy.trader.constant import Exchange
        from vnpy_ashare.domain.symbols import parse_stock_symbol

        rows: list[tuple[str, Exchange]] = []
        for line in self._symbols_edit.toPlainText().splitlines():
            text = line.strip()
            if not text:
                continue
            parsed = parse_stock_symbol(text)
            if parsed is None:
                continue
            rows.append((parsed.symbol, parsed.exchange))
            if len(rows) >= 5:
                break
        return rows

    def _apply_plan(self, plan: TradingPlanRecord) -> None:
        self._plan_id = plan.id
        parsed = datetime.strptime(plan.trade_date[:10], "%Y-%m-%d").date()
        self._date_edit.setDate(QtCore.QDate(parsed.year, parsed.month, parsed.day))
        self._max_pct_spin.setValue(round(plan.max_position_pct * 100))
        self._emotion_label.setText(plan.emotion_expected or "—")
        self._symbols_edit.setPlainText("\n".join(plan.watchlist_vt_symbols))
        self._notes_edit.setPlainText(plan.notes)
        status_map = {"draft": "草案", "active": "已激活", "archived": "已归档"}
        self._status_label.setText(status_map.get(plan.status, plan.status))

    def _load_active_plan(self) -> None:
        plan = load_active_trading_plan(self._trade_date())
        if plan is not None:
            self._apply_plan(plan)
            return
        self._plan_id = None
        self._status_label.setText("暂无激活计划")

    def _on_generate_draft(self) -> None:
        service = self._page._get_watchlist_service()
        draft = build_trading_plan_draft(
            watchlist_service=service,
            trade_date=self._trade_date() or _next_trade_date(),
        )
        self._max_pct_spin.setValue(int(round(float(draft.get("max_position_pct") or 0) * 100)))
        self._emotion_label.setText(str(draft.get("emotion_stage_label") or draft.get("emotion_expected") or "—"))
        symbols = draft.get("watchlist") or []
        lines = [str(item.get("vt_symbol") or "") for item in symbols if isinstance(item, dict)]
        self._symbols_edit.setPlainText("\n".join(line for line in lines if line))
        self._notes_edit.setPlainText(str(draft.get("notes") or ""))
        self._status_label.setText("草案（未保存）")

    def _ensure_plan_id(self) -> str | None:
        if self._plan_id:
            return self._plan_id
        plan_id = create_trading_plan(
            trade_date=self._trade_date(),
            emotion_expected=self._emotion_label.text() if self._emotion_label.text() != "—" else "",
            max_position_pct=self._max_pct_spin.value() / 100.0,
            notes=self._notes_edit.toPlainText().strip(),
            status="draft",
        )
        self._plan_id = plan_id
        return plan_id

    def _on_save(self) -> None:
        plan_id = self._ensure_plan_id()
        if plan_id is None:
            return
        update_trading_plan_meta(
            plan_id,
            max_position_pct=self._max_pct_spin.value() / 100.0,
            notes=self._notes_edit.toPlainText().strip(),
        )
        replace_trading_plan_symbols(plan_id, self._parse_symbols())
        self._status_label.setText("已保存草案")

    def _on_activate(self) -> None:
        self._on_save()
        if not self._plan_id:
            return
        if activate_trading_plan(self._plan_id):
            service = self._page._get_watchlist_service()
            added = 0
            if service is not None:
                added = sync_plan_to_observation_group(self._plan_id, service)
            if added:
                self._status_label.setText(f"已激活并同步观察组（新增 {added} 只）")
            else:
                self._status_label.setText("已激活（登记时将校验计划内）")
            groups = getattr(self._page, "_watchlist_groups", None)
            if groups is not None:
                groups.refresh_groups()

    def _on_sync_group(self) -> None:
        self._on_save()
        if not self._plan_id:
            return
        service = self._page._get_watchlist_service()
        if service is None:
            return
        added = sync_plan_to_observation_group(self._plan_id, service)
        self._status_label.setText(f"已同步观察组（新增 {added} 只）")
