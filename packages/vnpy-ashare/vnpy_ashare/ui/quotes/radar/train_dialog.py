"""雷达预测模型训练对话框。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.radar.predict.model_paths import (
    MODEL_FILE,
    lightgbm_available,
    lightgbm_unavailable_hint,
    load_manifest,
    manifest_model_age_days,
    manifest_model_caption,
    model_artifact_exists,
    should_retrain_predict_model,
)
from vnpy_ashare.ui.scheduler.dialog import show_scheduler_dialog
from vnpy_common.ui.dialog_shell import setup_responsive_dialog
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active


@dataclass(frozen=True)
class RadarPredictTrainStatus:
    headline: str
    detail: str
    can_train: bool
    retrain_recommended: bool


def build_radar_predict_train_status() -> RadarPredictTrainStatus:
    if not lightgbm_available():
        return RadarPredictTrainStatus(
            headline="LightGBM 未就绪",
            detail=lightgbm_unavailable_hint(),
            can_train=False,
            retrain_recommended=False,
        )
    manifest = load_manifest()
    if not model_artifact_exists():
        return RadarPredictTrainStatus(
            headline="尚无已训练模型",
            detail="需要本地全市场日 K。训练完成后将写入 ~/.vntrader/models/radar/。",
            can_train=True,
            retrain_recommended=True,
        )
    caption = manifest_model_caption(manifest)
    age = manifest_model_age_days(manifest)
    age_text = f"已训练 {age} 天" if age is not None else "训练时间未知"
    retrain = should_retrain_predict_model(max_age_days=30)
    headline = "建议重训" if retrain else "模型可用"
    detail_parts = [age_text]
    if caption:
        detail_parts.append(caption)
    detail_parts.append(f"文件：{MODEL_FILE}")
    if retrain:
        detail_parts.append("模型已超过 30 天，建议重新训练。")
    else:
        detail_parts.append("也可手动重训以更新因子权重。")
    return RadarPredictTrainStatus(
        headline=headline,
        detail=" · ".join(detail_parts),
        can_train=True,
        retrain_recommended=retrain,
    )


class RadarPredictTrainWorker(QtCore.QThread):
    finished_ok = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def run(self) -> None:
        try:
            from vnpy_ashare.quotes.radar.predict.predict_scan import run_predict_scan
            from vnpy_ashare.quotes.radar.predict.train_ranker import run_train_radar_ranker

            train = run_train_radar_ranker()
            if not train.success:
                self.failed.emit(train.message)
                return
            predict = run_predict_scan()
            message = f"{train.message}\n预测缓存已刷新 {len(predict.rows)} 只（{predict.model_label}）。"
            self.finished_ok.emit(message)
        except Exception as ex:
            self.failed.emit(str(ex))


class RadarPredictTrainDialog(QtWidgets.QDialog):
    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine,
        parent: QtWidgets.QWidget | None = None,
        *,
        on_trained: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._main_engine = main_engine
        self._event_engine = event_engine
        self._on_trained = on_trained
        self._worker: RadarPredictTrainWorker | None = None
        self._retired_workers: list[QtCore.QThread] = []

        self.setObjectName("RadarPredictTrainDialog")
        self.setWindowTitle("雷达模型训练")
        setup_responsive_dialog(self, parent, min_width=480, min_height=320, width_ratio=0.45, height_ratio=0.42)

        intro = QtWidgets.QLabel("训练雷达「未来·预测」卡的 LightGBM 截面模型。日常可由定时任务「雷达预测重训」自动维护。")
        intro.setObjectName("RadarPredictTrainIntro")
        intro.setWordWrap(True)

        self._headline = QtWidgets.QLabel("")
        self._headline.setObjectName("RadarPredictTrainHeadline")

        self._detail = QtWidgets.QLabel("")
        self._detail.setObjectName("RadarPredictTrainDetail")
        self._detail.setWordWrap(True)

        self._progress = QtWidgets.QLabel("")
        self._progress.setObjectName("RadarPredictTrainProgress")
        self._progress.hide()

        self._train_button = QtWidgets.QPushButton("立即训练")
        self._train_button.setObjectName("RadarPredictTrainButton")
        self._train_button.clicked.connect(self._start_train)

        scheduler_button = QtWidgets.QPushButton("打开定时任务…")
        scheduler_button.setObjectName("RadarPredictTrainSchedulerButton")
        scheduler_button.clicked.connect(self._open_scheduler)

        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(self.reject)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self._train_button)
        buttons.addWidget(scheduler_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(intro)
        layout.addWidget(self._headline)
        layout.addWidget(self._detail)
        layout.addWidget(self._progress)
        layout.addStretch(1)
        layout.addLayout(buttons)

        self._refresh_status()

    def _refresh_status(self) -> None:
        status = build_radar_predict_train_status()
        self._headline.setText(status.headline)
        self._detail.setText(status.detail)
        self._train_button.setEnabled(status.can_train and not thread_is_active(self._worker))
        if status.retrain_recommended and status.can_train:
            self._train_button.setText("立即重训")
        else:
            self._train_button.setText("立即训练")

    def _set_busy(self, busy: bool, *, message: str = "") -> None:
        self._train_button.setEnabled(not busy)
        if busy:
            self._progress.setText(message or "训练中，请稍候…")
            self._progress.show()
        else:
            self._progress.hide()
            self._progress.setText("")

    def _start_train(self) -> None:
        if thread_is_active(self._worker):
            return
        worker = RadarPredictTrainWorker(self)
        self._worker = worker
        worker.finished_ok.connect(self._on_train_ok)
        worker.failed.connect(self._on_train_failed)
        worker.finished.connect(self._on_worker_finished)
        self._set_busy(True)
        worker.start()

    def _on_train_ok(self, message: str) -> None:
        page_notify(self, message, level="success")
        self._refresh_status()
        if self._on_trained is not None:
            self._on_trained()

    def _on_train_failed(self, message: str) -> None:
        page_notify(self, message, level="warning")

    def _on_worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        release_thread(self._retired_workers, worker)
        self._set_busy(False)
        self._refresh_status()

    def _open_scheduler(self) -> None:
        show_scheduler_dialog(self._main_engine, self._event_engine, parent=self)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if thread_is_active(self._worker):
            event.ignore()
            page_notify(self, "训练进行中，请稍候完成", level="info")
            return
        super().closeEvent(event)


def show_radar_predict_train_dialog(
    main_engine: MainEngine,
    event_engine: EventEngine,
    parent: QtWidgets.QWidget | None = None,
    *,
    on_trained: Callable[[], None] | None = None,
) -> None:
    dialog = RadarPredictTrainDialog(
        main_engine,
        event_engine,
        parent=parent,
        on_trained=on_trained,
    )
    dialog.exec()
