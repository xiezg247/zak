"""选股页多因子配方面板（持久化 + 试跑，供定时任务引用）。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.screener.recipe import (
    DIMENSION_CATALOG,
    TriggerKind,
    default_config_for_trigger,
    list_dimension_ids,
    list_recipe_catalog,
    normalize_recipe_config,
    recipe_to_config,
    resolve_recipe,
    screen_recipe_from_config,
)
from vnpy_ashare.screener.recipe_store import delete_recipe, get_saved_recipe, save_recipe

_RECIPE_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole
_BUILTIN_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


class ScreenerRecipePanel(QtWidgets.QGroupBox):
    """多因子配方编辑区。"""

    run_requested = QtCore.Signal(object, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("多因子配方", parent)
        self.setObjectName("ScreenerRecipePanel")
        self._trigger_kind: TriggerKind = "intraday"
        self._dimension_rows: dict[str, tuple[QtWidgets.QCheckBox, QtWidgets.QDoubleSpinBox]] = {}
        self._loading = False
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        self._kind_tabs = QtWidgets.QTabBar()
        self._kind_tabs.addTab("盘中")
        self._kind_tabs.addTab("盘后")
        self._kind_tabs.currentChanged.connect(self._on_kind_changed)
        layout.addWidget(self._kind_tabs)

        self._recipe_combo = QtWidgets.QComboBox()
        self._recipe_combo.setObjectName("ToolbarCombo")
        self._recipe_combo.currentIndexChanged.connect(self._on_recipe_changed)
        layout.addWidget(self._recipe_combo)

        params_row = QtWidgets.QHBoxLayout()
        self._top_n_spin = QtWidgets.QSpinBox()
        self._top_n_spin.setRange(1, 200)
        self._top_n_spin.setValue(20)
        self._pool_spin = QtWidgets.QSpinBox()
        self._pool_spin.setRange(10, 500)
        self._pool_spin.setValue(50)
        self._min_dim_spin = QtWidgets.QSpinBox()
        self._min_dim_spin.setRange(1, 4)
        self._min_dim_spin.setValue(1)
        params_row.addWidget(QtWidgets.QLabel("Top N"))
        params_row.addWidget(self._top_n_spin)
        params_row.addWidget(QtWidgets.QLabel("候选池"))
        params_row.addWidget(self._pool_spin)
        params_row.addWidget(QtWidgets.QLabel("最少维度"))
        params_row.addWidget(self._min_dim_spin)
        params_row.addStretch()
        layout.addLayout(params_row)

        self._dimension_box = QtWidgets.QWidget()
        self._dimension_layout = QtWidgets.QFormLayout(self._dimension_box)
        self._dimension_layout.setSpacing(4)
        layout.addWidget(self._dimension_box)

        self._hint = QtWidgets.QLabel("保存后的配方可在「定时任务」页被引用。")
        self._hint.setObjectName("ScreenerHint")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(6)
        self._save_btn = QtWidgets.QPushButton("另存为")
        self._save_btn.setObjectName("SecondaryButton")
        self._save_btn.clicked.connect(self._save_recipe)
        self._delete_btn = QtWidgets.QPushButton("删除")
        self._delete_btn.setObjectName("SecondaryButton")
        self._delete_btn.clicked.connect(self._delete_recipe)
        self._run_btn = QtWidgets.QPushButton("试跑配方")
        self._run_btn.setObjectName("SecondaryButton")
        self._run_btn.clicked.connect(self._run_recipe)
        action_row.addWidget(self._save_btn)
        action_row.addWidget(self._delete_btn)
        action_row.addWidget(self._run_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

    def reload(self) -> None:
        selected_id = self.current_recipe_id()
        self._reload_recipe_combo(selected_id)

    def current_recipe_id(self) -> str | None:
        data = self._recipe_combo.currentData(_RECIPE_ID_ROLE)
        return str(data) if data else None

    def _on_kind_changed(self, index: int) -> None:
        self._trigger_kind = "intraday" if index == 0 else "post_close"
        self._reload_recipe_combo(None)

    def _reload_recipe_combo(self, selected_id: str | None) -> None:
        self._loading = True
        self._recipe_combo.blockSignals(True)
        self._recipe_combo.clear()
        restore_index = 0
        for idx, entry in enumerate(list_recipe_catalog(trigger_kind=self._trigger_kind)):
            self._recipe_combo.addItem(entry.display_name)
            row = self._recipe_combo.count() - 1
            self._recipe_combo.setItemData(row, entry.recipe_id, _RECIPE_ID_ROLE)
            self._recipe_combo.setItemData(row, entry.builtin, _BUILTIN_ROLE)
            if selected_id and entry.recipe_id == selected_id:
                restore_index = idx
        self._recipe_combo.setCurrentIndex(restore_index if self._recipe_combo.count() else -1)
        self._recipe_combo.blockSignals(False)
        self._loading = False
        self._load_current_recipe()
        self._rebuild_dimension_editor()

    def _on_recipe_changed(self, _index: int) -> None:
        if self._loading:
            return
        self._load_current_recipe()
        self._update_action_state()

    def _load_current_recipe(self) -> None:
        recipe_id = self.current_recipe_id()
        if not recipe_id:
            return
        recipe = resolve_recipe(recipe_id)
        if recipe is None:
            return
        if recipe.builtin:
            config = recipe_to_config(recipe)
        else:
            saved = get_saved_recipe(recipe_id)
            config = dict(saved.config) if saved else recipe_to_config(recipe)
        self._apply_config(config)
        self._update_action_state()

    def _apply_config(self, config: dict[str, Any]) -> None:
        self._loading = True
        self._top_n_spin.setValue(int(config.get("top_n") or 20))
        self._pool_spin.setValue(int(config.get("pool_size") or 50))
        self._min_dim_spin.setValue(int(config.get("min_dimensions") or 1))
        by_id = {str(item.get("dimension_id")): item for item in config.get("dimensions") or []}
        for dim_id, (enabled_box, weight_spin) in self._dimension_rows.items():
            item = by_id.get(dim_id, {})
            enabled_box.setChecked(bool(item.get("enabled", dim_id in by_id)))
            weight_spin.setValue(float(item.get("weight") or 0))
        self._loading = False

    def _rebuild_dimension_editor(self) -> None:
        while self._dimension_layout.rowCount():
            self._dimension_layout.removeRow(0)
        self._dimension_rows.clear()

        defaults = default_config_for_trigger(self._trigger_kind)
        default_weights = {
            str(item["dimension_id"]): float(item.get("weight") or 0)
            for item in defaults.get("dimensions") or []
        }

        for dim_id in list_dimension_ids(trigger_kind=self._trigger_kind):
            label = str(DIMENSION_CATALOG[dim_id]["label"])
            enabled_box = QtWidgets.QCheckBox(label)
            enabled_box.setChecked(dim_id in default_weights)
            weight_spin = QtWidgets.QDoubleSpinBox()
            weight_spin.setRange(0, 1)
            weight_spin.setDecimals(2)
            weight_spin.setSingleStep(0.05)
            weight_spin.setValue(default_weights.get(dim_id, 0.25))
            enabled_box.toggled.connect(
                lambda checked, spin=weight_spin: spin.setEnabled(checked)
            )
            weight_spin.setEnabled(enabled_box.isChecked())

            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(enabled_box)
            row_layout.addStretch()
            row_layout.addWidget(QtWidgets.QLabel("权重"))
            row_layout.addWidget(weight_spin)
            self._dimension_layout.addRow(row_widget)
            self._dimension_rows[dim_id] = (enabled_box, weight_spin)

        self._load_current_recipe()

    def _collect_config(self) -> dict[str, Any]:
        dimensions: list[dict[str, Any]] = []
        for dim_id, (enabled_box, weight_spin) in self._dimension_rows.items():
            dimensions.append(
                {
                    "dimension_id": dim_id,
                    "label": str(DIMENSION_CATALOG[dim_id]["label"]),
                    "weight": weight_spin.value(),
                    "enabled": enabled_box.isChecked(),
                }
            )
        return normalize_recipe_config(
            {
                "top_n": self._top_n_spin.value(),
                "pool_size": self._pool_spin.value(),
                "min_dimensions": self._min_dim_spin.value(),
                "dimensions": dimensions,
            }
        )

    def build_runtime_recipe(self):
        recipe_id = self.current_recipe_id() or "preview"
        is_builtin = bool(self._recipe_combo.currentData(_BUILTIN_ROLE))
        if is_builtin:
            resolved = resolve_recipe(recipe_id)
            name = resolved.name if resolved else "预览"
        else:
            saved = get_saved_recipe(recipe_id)
            name = saved.name if saved else "预览"
        return screen_recipe_from_config(
            recipe_id=recipe_id,
            name=name,
            trigger_kind=self._trigger_kind,
            config=self._collect_config(),
            builtin=False,
        )

    def _update_action_state(self) -> None:
        is_builtin = bool(self._recipe_combo.currentData(_BUILTIN_ROLE))
        self._save_btn.setText("另存为" if is_builtin else "保存")
        self._delete_btn.setEnabled(not is_builtin and self.current_recipe_id() is not None)

    def _save_recipe(self) -> None:
        is_builtin = bool(self._recipe_combo.currentData(_BUILTIN_ROLE))
        recipe_id = None if is_builtin else self.current_recipe_id()
        title = "另存为配方" if is_builtin else "保存配方"
        default_name = ""
        if not is_builtin:
            saved = get_saved_recipe(str(recipe_id))
            default_name = saved.name if saved else ""
        text, ok = QtWidgets.QInputDialog.getText(self, title, "配方名称", text=default_name)
        if not ok or not text.strip():
            return
        try:
            config = self._collect_config()
            saved = save_recipe(
                text.strip(),
                trigger_kind=self._trigger_kind,
                config=config,
                recipe_id=recipe_id,
            )
        except ValueError as ex:
            QtWidgets.QMessageBox.warning(self, "提示", str(ex))
            return
        self._reload_recipe_combo(saved.id)

    def _delete_recipe(self) -> None:
        recipe_id = self.current_recipe_id()
        if not recipe_id or bool(self._recipe_combo.currentData(_BUILTIN_ROLE)):
            return
        name = self._recipe_combo.currentText()
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            f"删除配方「{name}」？\n引用该配方的定时任务将失效。",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        delete_recipe(recipe_id)
        self._reload_recipe_combo(None)

    def _run_recipe(self) -> None:
        try:
            recipe = self.build_runtime_recipe()
        except ValueError as ex:
            QtWidgets.QMessageBox.warning(self, "提示", str(ex))
            return
        recipe_id = self.current_recipe_id() or recipe.recipe_id
        self.run_requested.emit(recipe, recipe_id)
