"""QSS：SETTINGS_DIALOG。"""

SETTINGS_DIALOG_STYLESHEET = """
QDialog#SettingsDialog {
    background-color: #1a1a1a;
    color: #e0e0e0;
}
QScrollArea#SettingsScroll,
QWidget#SettingsScrollBody {
    background-color: transparent;
    border: none;
}
QLabel#SettingsHint {
    color: #8a8a95;
    font-size: 12px;
    padding: 8px 10px;
    background-color: #1e1e24;
    border: 1px solid #2d2d32;
    border-radius: 6px;
}
QLabel#SettingsMeta {
    color: #9a9aa5;
    font-size: 12px;
    margin-bottom: 4px;
}
QLabel#SettingsSubheading {
    color: #8a8aaf;
    font-size: 12px;
    font-weight: bold;
    margin-top: 4px;
}
QPushButton#SettingsSegmentLeft,
QPushButton#SettingsSegmentRight {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    padding: 6px 20px;
    color: #a0a0a8;
    font-size: 12px;
    min-width: 88px;
}
QPushButton#SettingsSegmentLeft {
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right: none;
}
QPushButton#SettingsSegmentRight {
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}
QPushButton#SettingsSegmentLeft:checked,
QPushButton#SettingsSegmentRight:checked {
    background-color: #2a5a9e;
    border-color: #4a9eff;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#SettingsSegmentLeft:hover:!checked,
QPushButton#SettingsSegmentRight:hover:!checked {
    background-color: #2f2f2f;
    color: #d0d0d8;
}
QGroupBox#SettingsGroup {
    background-color: #1e1e22;
    border: 1px solid #2d2d32;
    border-radius: 6px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-size: 12px;
    color: #a0a0a0;
}
QDialog#SettingsDialog QGroupBox#SettingsGroup {
    min-height: 48px;
}
QGroupBox#SettingsGroup::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: #8a8aaf;
    font-weight: bold;
}
QTableWidget#SettingsEnvTable {
    background-color: #1a1a1a;
    gridline-color: #2a2a2a;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    font-size: 12px;
    alternate-background-color: #1e1e22;
    selection-background-color: #2a4a7a;
    selection-color: #ffffff;
}
QTableWidget#SettingsEnvTable::item {
    padding-left: 10px;
    padding-right: 10px;
    border: none;
}
QTableWidget#SettingsEnvTable::item:alternate {
    background-color: #1e1e22;
}
QTableWidget#SettingsEnvTable::item:selected {
    background-color: #2a4a7a;
    color: #ffffff;
}
QTableWidget#SettingsEnvTable QHeaderView::section {
    background-color: #252525;
    color: #a0a0a0;
    padding-left: 10px;
    padding-right: 10px;
    border: none;
    border-bottom: 1px solid #333;
    border-right: 1px solid #333;
    font-size: 12px;
    min-height: 34px;
}
QLabel#SettingsFormLabel {
    color: #9a9aa5;
    font-size: 12px;
    min-width: 108px;
}
QSpinBox#SettingsInput {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #f0f0f0;
    min-height: 28px;
    font-size: 13px;
}
QSpinBox#SettingsInput::up-button,
QSpinBox#SettingsInput::down-button {
    width: 16px;
    background-color: #2d2d2d;
    border: none;
}
QLineEdit#SettingsInput,
QComboBox#SettingsInput {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px 10px;
    color: #f0f0f0;
    min-height: 28px;
    font-size: 13px;
}
QLineEdit#SettingsInput:focus,
QComboBox#SettingsInput:focus {
    border-color: #4a9eff;
}
QLineEdit#SettingsInput:read-only {
    color: #a0a0a8;
    background-color: #1e1e22;
    border-color: #2d2d32;
}
QSpinBox#SettingsInput:focus {
    border-color: #4a9eff;
}
QComboBox#SettingsInput::drop-down {
    border: none;
    width: 22px;
}
QComboBox#SettingsInput QAbstractItemView {
    background-color: #2a2a2a;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    selection-background-color: #3d6a9e;
}
QCheckBox#SettingsCheck {
    color: #d8d8de;
    spacing: 8px;
}
QPushButton#SettingsPrimaryButton {
    background-color: #2a5a9e;
    border: 1px solid #4a9eff;
    border-radius: 4px;
    padding: 6px 18px;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#SettingsPrimaryButton:hover {
    background-color: #3a6fbf;
}
QPushButton#SettingsSecondaryButton {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px 16px;
    color: #c8c8d0;
}
QPushButton#SettingsSecondaryButton:hover {
    background-color: #353535;
    color: #f0f0f0;
}
"""
