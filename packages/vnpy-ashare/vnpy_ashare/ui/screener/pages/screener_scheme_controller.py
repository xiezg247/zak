"""条件选股页方案保存与删除。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.screener.run.runner import build_industry_scheme_config
from vnpy_common.ui.feedback import confirm_action

if TYPE_CHECKING:
    from vnpy_ashare.ui.screener.pages.screener_page import ScreenerPageWidget


class ScreenerSchemeController:
    """内置 / 自定义 / 行业方案的持久化。"""

    def __init__(self, page: ScreenerPageWidget) -> None:
        self._page = page

    def save_scheme(self) -> None:
        page = self._page
        service = page._screening_service()
        if service is None:
            page._toast.warning("选股服务未就绪")
            return

        label = page.preset_combo.currentText()
        scheme_id = page._current_scheme_id()
        industry = page.industry_edit.text().strip()

        if label.startswith("我的 · ") and scheme_id:
            for scheme in service.list_schemes():
                if scheme.id != scheme_id:
                    continue
                if str(scheme.config.get("kind") or "") != "industry":
                    page._toast.info("该方案不是行业成分类型，请新建保存")
                    return
                if not industry:
                    page._toast.warning("请输入行业名称")
                    return
                try:
                    service.save_scheme(
                        scheme.name,
                        build_industry_scheme_config(industry, top_n=page.top_n_spin.value()),
                        scheme_id=scheme_id,
                    )
                    page._reload_preset_combo()
                    page._append_action_log(f"已更新行业方案：{scheme.name}")
                    page._toast.success(f"已更新方案：{scheme.name}")
                except Exception as ex:
                    page._toast.error(str(ex))
                return
            page._toast.info("方案不存在或已删除")
            return

        if industry:
            default_name = f"{industry}成分"
            text, ok = QtWidgets.QInputDialog.getText(page, "保存行业方案", "方案名称", text=default_name)
            if not ok or not text.strip():
                return
            try:
                service.save_scheme(
                    text.strip(),
                    build_industry_scheme_config(industry, top_n=page.top_n_spin.value()),
                )
                page._reload_preset_combo()
                saved_name = f"我的 · {text.strip()}"
                index = page.preset_combo.findText(saved_name)
                if index >= 0:
                    page.preset_combo.setCurrentIndex(index)
                page._append_action_log(f"已保存行业方案：{text.strip()}")
                page._toast.success(f"已保存行业方案：{text.strip()}")
            except Exception as ex:
                page._toast.error(str(ex))
            return

        if label.startswith("我的 · "):
            page._toast.info("请选择内置方案或填写行业名称后再保存")
            return
        text, ok = QtWidgets.QInputDialog.getText(page, "保存方案", "方案名称")
        if not ok or not text.strip():
            return
        request, _ = page._build_request()
        if request is None or not request.preset:
            return
        try:
            service.save_scheme(text.strip(), service.build_scheme_config(request))
            page._reload_preset_combo()
            saved_name = f"我的 · {text.strip()}"
            index = page.preset_combo.findText(saved_name)
            if index >= 0:
                page.preset_combo.setCurrentIndex(index)
            page._append_action_log(f"已保存方案：{text.strip()}")
            page._toast.success(f"已保存方案：{text.strip()}")
        except Exception as ex:
            page._toast.error(str(ex))

    def delete_scheme(self) -> None:
        page = self._page
        scheme_id = page._current_scheme_id()
        if not scheme_id:
            page._toast.info("请先选择「我的 · …」方案")
            return
        if not confirm_action(
            page,
            "确认删除",
            f"删除方案「{page.preset_combo.currentText()}」？",
            confirm_text="删除",
            destructive=True,
        ):
            return
        service = page._screening_service()
        if service is None:
            page._toast.warning("选股服务未就绪")
            return
        service.delete_scheme(scheme_id)
        page._reload_preset_combo()
        page._append_action_log("方案已删除")
        page._toast.success("方案已删除")
