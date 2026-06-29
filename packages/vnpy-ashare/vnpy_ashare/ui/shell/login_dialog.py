"""启动登录：仅 default 时自动登录，多用户时弹窗。"""

from __future__ import annotations

import os

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_ashare.storage.auth.users import list_active_users, login
from vnpy_common.auth.context import set_current_user
from vnpy_common.paths import QSETTINGS_ORG


class LoginDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录 zak")
        self.setModal(True)
        self._settings = QtCore.QSettings(QSETTINGS_ORG, "auth")
        self._user: str | None = None

        layout = QtWidgets.QFormLayout(self)
        self.username_edit = QtWidgets.QLineEdit()
        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        saved = self._settings.value("last_username")
        if isinstance(saved, str) and saved:
            self.username_edit.setText(saved)
        layout.addRow("用户名", self.username_edit)
        layout.addRow("密码", self.password_edit)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_accept(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        user = login(username, password)
        if user is None:
            QtWidgets.QMessageBox.warning(self, "登录失败", "用户名或密码错误")
            return
        self._settings.setValue("last_username", user.username)
        set_current_user(user.id)
        self._user = user.id
        self.accept()

    @property
    def user_id(self) -> str | None:
        return self._user


def _skip_login_dialog() -> bool:
    if os.environ.get("ZAK_REQUIRE_LOGIN", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if os.environ.get("ZAK_SKIP_LOGIN", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    users = list_active_users()
    return len(users) <= 1


def ensure_logged_in(parent: QtWidgets.QWidget | None = None) -> bool:
    """仅 default 单用户时自动登录；多用户或 ZAK_SKIP_LOGIN=0 且已建号时弹窗。"""
    if _skip_login_dialog():
        set_current_user(get_user_id())
        return True
    dialog = LoginDialog(parent)
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return False
    return dialog.user_id is not None
