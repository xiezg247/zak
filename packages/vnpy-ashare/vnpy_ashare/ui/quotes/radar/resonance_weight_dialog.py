"""雷达共振权重设置对话框。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.quotes.radar.radar_resonance_prefs import (
    SHORT_TERM_RADAR_RESONANCE_WEIGHTS,
    DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS,
    list_radar_resonance_weight_items,
    load_radar_resonance_weights,
    save_radar_resonance_weights,
)


class RadarResonanceWeightDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("共振权重")
        self.setMinimumWidth(360)

        intro = QtWidgets.QLabel(
            "调整各卡片在共振列表中的权重。发现类权重越高，共振排序越偏向盘中异动。",
        )
        intro.setWordWrap(True)

        form = QtWidgets.QFormLayout()
        self._spinboxes: dict[str, QtWidgets.QDoubleSpinBox] = {}
        current = load_radar_resonance_weights()
        for card_id, label, default in list_radar_resonance_weight_items():
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.1, 5.0)
            spin.setSingleStep(0.25)
            spin.setDecimals(2)
            spin.setValue(float(current.get(card_id, default)))
            self._spinboxes[card_id] = spin
            form.addRow(label, spin)

        preset_row = QtWidgets.QHBoxLayout()
        short_term_btn = QtWidgets.QPushButton("短线龙头预设")
        short_term_btn.setObjectName("SecondaryButton")
        short_term_btn.setToolTip("提高发现/龙头卡权重，降低展望区权重")
        short_term_btn.clicked.connect(self._apply_short_term_preset)
        reset_btn = QtWidgets.QPushButton("恢复默认")
        reset_btn.setObjectName("SecondaryButton")
        reset_btn.clicked.connect(self._apply_default_preset)
        preset_row.addWidget(short_term_btn)
        preset_row.addWidget(reset_btn)
        preset_row.addStretch()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addLayout(preset_row)
        layout.addWidget(buttons)

    def _apply_weight_values(self, weights: dict[str, float]) -> None:
        for card_id, spin in self._spinboxes.items():
            spin.setValue(float(weights.get(card_id, spin.value())))

    def _apply_short_term_preset(self) -> None:
        self._apply_weight_values(SHORT_TERM_RADAR_RESONANCE_WEIGHTS)

    def _apply_default_preset(self) -> None:
        self._apply_weight_values(DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS)

    def save(self) -> None:
        weights = {card_id: spin.value() for card_id, spin in self._spinboxes.items()}
        save_radar_resonance_weights(weights)
