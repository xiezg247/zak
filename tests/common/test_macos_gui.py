"""macOS GUI 启动适配单元测试。"""

from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

from vnpy_common.platform import macos_gui


def test_configure_macos_before_qt_sets_os_activity_mode_on_darwin() -> None:
    with patch.object(macos_gui, "is_macos", return_value=True):
        with patch.dict("os.environ", {}, clear=True):
            macos_gui.configure_macos_before_qt()
            assert macos_gui.os.environ.get("OS_ACTIVITY_MODE") == "disable"


def test_configure_macos_before_qt_noop_on_linux() -> None:
    with patch.object(macos_gui, "is_macos", return_value=False):
        macos_gui.configure_macos_before_qt()


def test_promote_macos_gui_process_noop_on_linux() -> None:
    with patch.object(macos_gui, "is_macos", return_value=False):
        assert macos_gui.promote_macos_gui_process() is False


def test_is_benign_macos_gui_log() -> None:
    assert macos_gui.is_benign_macos_gui_log(
        "2026-06-24 python[1:2] TSMSendMessageToUIServer: "
        "CFMessagePortSendRequest FAILED(-1) to send to port com.apple.tsm.uiserver\n"
    )
    assert macos_gui.is_benign_macos_gui_log(
        "2026-06-24 python[52096:53223772] error messaging the mach port for IMKCFRunLoopWakeUpReliable\n"
    )
    assert macos_gui.is_benign_macos_gui_log(
        "2026-06-24 python[60255:53262380] TSM AdjustCapsLockLEDForKeyTransitionHandling - "
        "_ISSetPhysicalKeyboardCapsLockLED Inhibit\n"
    )
    assert not macos_gui.is_benign_macos_gui_log("real application error\n")


def test_install_macos_gui_log_filter_suppresses_imk_noise() -> None:
    original = sys.stderr
    buffer = io.StringIO()
    sys.stderr = buffer
    try:
        with (
            patch.object(macos_gui, "is_macos", return_value=True),
            patch.object(macos_gui, "_install_native_stderr_line_filter"),
            patch.object(macos_gui, "_stderr_filter_installed", False),
        ):
            macos_gui.install_macos_gui_log_filter()
            sys.stderr.write(
                "2026-06-24 python[52096:53223772] error messaging the mach port for "
                "IMKCFRunLoopWakeUpReliable\n"
            )
            sys.stderr.write("real error line\n")
            filtered = buffer.getvalue()
        assert "IMKCFRunLoopWakeUpReliable" not in filtered
        assert "real error line\n" in filtered
    finally:
        sys.stderr = original
        macos_gui._stderr_filter_installed = False


def test_promote_macos_gui_process_calls_transform_on_darwin() -> None:
    fake_lib = MagicMock()
    fake_lib.GetCurrentProcess.return_value = 0
    fake_lib.TransformProcessType.return_value = 0
    with (
        patch.object(macos_gui, "is_macos", return_value=True),
        patch.object(macos_gui.ctypes, "CDLL", return_value=fake_lib),
    ):
        assert macos_gui.promote_macos_gui_process() is True
    fake_lib.TransformProcessType.assert_called_once()
