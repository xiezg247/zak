"""配方评分 / 动量 / 恐贪调制参数对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.screener.recipe_tuning_prefs import (
    RecipeTuningPrefs,
    load_recipe_tuning_prefs,
    save_recipe_tuning_prefs,
)
from vnpy_ashare.screener.sentiment.sentiment_gate import try_fetch_fear_greed_index


class RecipeTuningDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("配方评分参数")
        self.setMinimumWidth(420)

        intro = QtWidgets.QLabel(
            "调整综合分混合比例、动量涨幅区间与恐贪环境调制。环境变量 RECIPE_* / MOMENTUM_* 仍可覆盖对应项。",
        )
        intro.setWordWrap(True)

        self._blend_spin = QtWidgets.QDoubleSpinBox()
        self._blend_spin.setRange(0.0, 1.0)
        self._blend_spin.setSingleStep(0.05)
        self._blend_spin.setDecimals(2)
        self._blend_spin.setToolTip("0=纯排名分，1=纯指标分位，0.5=均衡")

        self._momentum_min_spin = QtWidgets.QDoubleSpinBox()
        self._momentum_min_spin.setRange(0.0, 20.0)
        self._momentum_min_spin.setDecimals(2)
        self._momentum_min_spin.setSuffix("%")

        self._momentum_max_spin = QtWidgets.QDoubleSpinBox()
        self._momentum_max_spin.setRange(0.5, 30.0)
        self._momentum_max_spin.setDecimals(2)
        self._momentum_max_spin.setSuffix("%")

        self._momentum_fear_max_spin = QtWidgets.QDoubleSpinBox()
        self._momentum_fear_max_spin.setRange(0.5, 30.0)
        self._momentum_fear_max_spin.setDecimals(2)
        self._momentum_fear_max_spin.setSuffix("%")
        self._momentum_fear_max_spin.setToolTip("极度恐惧时动量涨幅上限")

        self._breakout_lookback_spin = QtWidgets.QSpinBox()
        self._breakout_lookback_spin.setRange(0, 60)
        self._breakout_lookback_spin.setToolTip("0=仅昨收突破，>0 要求突破近 N 日高点")

        self._volume_dedup_spin = QtWidgets.QDoubleSpinBox()
        self._volume_dedup_spin.setRange(0.0, 1.0)
        self._volume_dedup_spin.setSingleStep(0.05)
        self._volume_dedup_spin.setDecimals(2)
        self._volume_dedup_spin.setToolTip("同票命中量比+放量时，放量得分乘以此系数")

        score_form = QtWidgets.QFormLayout()
        score_form.addRow("指标混合 blend", self._blend_spin)
        score_form.addRow("动量最低涨幅", self._momentum_min_spin)
        score_form.addRow("动量最高涨幅", self._momentum_max_spin)
        score_form.addRow("恐惧时动量上限", self._momentum_fear_max_spin)
        score_form.addRow("突破回看天数", self._breakout_lookback_spin)
        score_form.addRow("放量去重系数", self._volume_dedup_spin)

        self._sentiment_enabled = QtWidgets.QCheckBox("启用恐贪环境调制（盘中配方 composite）")

        self._sentiment_status = QtWidgets.QLabel("")
        self._sentiment_status.setObjectName("ScreenerHint")
        self._sentiment_status.setWordWrap(True)

        self._sf_momentum = _coef_spin()
        self._sf_sector = _coef_spin()
        self._sf_breakout = _coef_spin()
        self._fear_momentum = _coef_spin()
        self._sg_turnover = _coef_spin()
        self._sg_volume = _coef_spin()
        self._g_turnover = _coef_spin()

        sentiment_form = QtWidgets.QFormLayout()
        sentiment_form.addRow("极度恐惧·动量削弱", self._sf_momentum)
        sentiment_form.addRow("极度恐惧·板块削弱", self._sf_sector)
        sentiment_form.addRow("极度恐惧·突破削弱", self._sf_breakout)
        sentiment_form.addRow("恐惧·动量削弱", self._fear_momentum)
        sentiment_form.addRow("极度贪婪·换手削弱", self._sg_turnover)
        sentiment_form.addRow("极度贪婪·放量削弱", self._sg_volume)
        sentiment_form.addRow("贪婪·换手削弱", self._g_turnover)

        tabs = QtWidgets.QTabWidget()
        score_tab = QtWidgets.QWidget()
        score_tab_layout = QtWidgets.QVBoxLayout(score_tab)
        score_tab_layout.addLayout(score_form)
        score_tab_layout.addStretch()
        tabs.addTab(score_tab, "评分与动量")

        sentiment_tab = QtWidgets.QWidget()
        sentiment_layout = QtWidgets.QVBoxLayout(sentiment_tab)
        sentiment_layout.addWidget(self._sentiment_enabled)
        sentiment_layout.addWidget(self._sentiment_status)
        sentiment_layout.addLayout(sentiment_form)
        sentiment_layout.addStretch()
        tabs.addTab(sentiment_tab, "恐贪调制")

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        self._load_prefs()
        self._refresh_sentiment_status()

    def _load_prefs(self) -> None:
        prefs = load_recipe_tuning_prefs()
        self._blend_spin.setValue(prefs.metric_score_blend)
        self._momentum_min_spin.setValue(prefs.momentum_min_change_pct)
        self._momentum_max_spin.setValue(prefs.momentum_max_change_pct)
        self._momentum_fear_max_spin.setValue(prefs.momentum_fear_max_change_pct)
        self._breakout_lookback_spin.setValue(prefs.breakout_lookback_days)
        self._volume_dedup_spin.setValue(prefs.volume_liquidity_dedup_factor)
        self._sentiment_enabled.setChecked(prefs.sentiment_gate_enabled)
        self._sf_momentum.setValue(prefs.extreme_fear_momentum)
        self._sf_sector.setValue(prefs.extreme_fear_sector)
        self._sf_breakout.setValue(prefs.extreme_fear_breakout)
        self._fear_momentum.setValue(prefs.fear_momentum)
        self._sg_turnover.setValue(prefs.extreme_greed_turnover)
        self._sg_volume.setValue(prefs.extreme_greed_volume_surge)
        self._g_turnover.setValue(prefs.greed_turnover)

    def _refresh_sentiment_status(self) -> None:
        snapshot = try_fetch_fear_greed_index(include_components=True)
        if snapshot is None:
            self._sentiment_status.setText("当前恐贪指数暂不可用（将跳过环境调制）。")
            return
        parts = [f"当前恐贪 {snapshot.index:.0f}（{snapshot.label}）"]
        if snapshot.components:
            comp_bits = [f"{item.name} {item.score:.0f}" for item in snapshot.components[:4]]
            parts.append("分项：" + "、".join(comp_bits))
        self._sentiment_status.setText(" · ".join(parts))

    def save(self) -> RecipeTuningPrefs:
        prefs = RecipeTuningPrefs(
            metric_score_blend=float(self._blend_spin.value()),
            momentum_min_change_pct=float(self._momentum_min_spin.value()),
            momentum_max_change_pct=float(self._momentum_max_spin.value()),
            momentum_fear_max_change_pct=float(self._momentum_fear_max_spin.value()),
            breakout_lookback_days=int(self._breakout_lookback_spin.value()),
            volume_liquidity_dedup_factor=float(self._volume_dedup_spin.value()),
            sentiment_gate_enabled=self._sentiment_enabled.isChecked(),
            extreme_fear_momentum=float(self._sf_momentum.value()),
            extreme_fear_sector=float(self._sf_sector.value()),
            extreme_fear_breakout=float(self._sf_breakout.value()),
            fear_momentum=float(self._fear_momentum.value()),
            extreme_greed_turnover=float(self._sg_turnover.value()),
            extreme_greed_volume_surge=float(self._sg_volume.value()),
            greed_turnover=float(self._g_turnover.value()),
        )
        save_recipe_tuning_prefs(prefs)
        return prefs


def _coef_spin() -> QtWidgets.QDoubleSpinBox:
    spin = QtWidgets.QDoubleSpinBox()
    spin.setRange(0.0, 0.5)
    spin.setSingleStep(0.01)
    spin.setDecimals(3)
    spin.setToolTip("从该维度贡献分中扣除的比例系数")
    return spin
