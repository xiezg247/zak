"""板块资金 AI 上下文与 Ask AI 请求。"""

from __future__ import annotations

from vnpy.event import Event

from vnpy_ashare.app.engine_access import get_quote_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.market.sector_flow import SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.services.sector_flow import format_sector_net_flow_yi
from vnpy_ashare.services.sector_flow_outlook import format_continuation_ai_lines
from vnpy_ashare.services.sector_flow_outlook_strategy import classify_sector_resonance
from vnpy_ashare.services.sector_flow_rotation import format_rotation_ai_lines
from vnpy_ashare.ui.sector_flow.controller.base import SectorFlowControllerBase
from vnpy_common.ui.feedback import page_notify


class SectorFlowAiMixin(SectorFlowControllerBase):
    def _on_sector_ai_requested(self, sector: object) -> None:
        if not isinstance(sector, SectorFlowRow):
            return
        snap = self._last_snapshot
        if snap is None or not snap.rows:
            page_notify(self._page, "请先刷新板块数据", level="warning")
            return
        if self._event_engine is None:
            return
        continuation = self._continuation_row_for_sector(sector)
        scan_row = None
        if self._last_outlook is not None:
            for item in self._last_outlook.sector_scans:
                if item.sector.sector_id == sector.sector_id:
                    scan_row = item
                    break
        kind_label = "概念" if sector.sector_kind == "concept" else "行业"
        strategy_label = self._outlook_strategy_label()
        lines = [
            f"请解读「{sector.name}」{kind_label}板块的资金延续与策略信号（统计情景，非资金预测）。",
            f"策略口径：{strategy_label}（成分股直扫，非雷达全球展望池）。",
        ]
        if continuation is not None:
            day_tags = " / ".join(f"T+{index + 1}{day.bias}({day.strength:.2f})" for index, day in enumerate(continuation.days))
            lines.append(f"资金延续：{continuation.headline_pattern} {day_tags} — {continuation.rationale}")
        else:
            lines.append("资金延续：暂无加载数据")
        if scan_row is not None:
            day_tags = " / ".join(f"T+{index + 1}{day.bias}({day.strength:.2f})" for index, day in enumerate(scan_row.days))
            resonance = classify_sector_resonance(continuation, scan_row)
            lines.append(f"成分策略：{scan_row.headline_pattern} {day_tags} — {scan_row.rationale}")
            lines.append(f"延续与策略 T+1 共振：{resonance}")
        else:
            lines.append("成分策略：尚未扫描，请说明仅可基于资金延续解读")
        self._event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt="\n".join(lines), source_page="板块资金"),
            )
        )

    def _publish_ai_context(self, snapshot: SectorFlowSnapshot | None = None) -> None:
        quote_service = get_quote_service(self._main_engine)
        if quote_service is None:
            return
        extra_lines = ["板块资金监控页"]
        snap = snapshot or self._last_snapshot
        if snap and snap.rows:
            kind_label = "概念" if snap.sector_kind == "concept" else "行业"
            mode_labels = {"intraday": "盘中估算", "official_dc": "日终东财", "official_ths": "日终同花顺", "official_sw": "日终申万"}
            extra_lines.append(f"{kind_label}·{mode_labels.get(snap.data_mode, snap.data_mode)}")
            extra_lines.append(
                f"净流入 {snap.top_inflow_name} {format_sector_net_flow_yi(snap.top_inflow_yi)}；"
                f"净流出 {snap.top_outflow_name} {format_sector_net_flow_yi(snap.top_outflow_yi)}"
            )
            rotation = self._last_rotation
            if rotation and rotation.rows:
                extra_lines.extend(format_rotation_ai_lines(rotation, limit=5))
            outlook = self._last_outlook
            if outlook and outlook.continuation.rows:
                extra_lines.extend(format_continuation_ai_lines(outlook.continuation, limit=5))
            for row in snap.rows[:8]:
                leader = f" 龙头{row.leader_stock}" if row.leader_stock else ""
                extra_lines.append(f"{row.name} 强度{row.strength:.1f} 涨幅{row.change_pct:+.2f}% 主力{row.net_flow_yi:+.2f}亿({row.flow_source}){leader}")
        quote_service.publish_quote_context(
            page="板块资金",
            signal_extra="\n".join(extra_lines),
        )

    def _request_ai(self) -> None:
        snap = self._last_snapshot
        if snap is None or not snap.rows:
            page_notify(self._page, "请先刷新板块数据", level="warning")
            return
        if self._event_engine is None:
            return
        kind_label = "概念" if snap.sector_kind == "concept" else "行业"
        mode_note = {
            "intraday": "盘中为行情聚合估算",
            "official_dc": "东财官方日终板块资金",
            "official_ths": "同花顺官方日终概念资金",
        }.get(snap.data_mode, "")
        lines = [
            f"请解读当前{kind_label}板块资金结构：哪些板块资金净流入/流出突出，与涨幅是否一致，短线需关注什么。",
            f"数据口径：{mode_note}，请说明不确定性。",
        ]
        rotation = self._last_rotation
        if rotation and rotation.rows and rotation.sector_kind == snap.sector_kind:
            lines.append("近15日资金轮动：")
            lines.extend(format_rotation_ai_lines(rotation, limit=10))
        outlook = self._last_outlook
        if outlook and outlook.continuation.rows and outlook.continuation.sector_kind == snap.sector_kind:
            lines.append("未来3日资金延续展望（统计情景，非预测）：")
            lines.extend(format_continuation_ai_lines(outlook.continuation, limit=10))
        lines.append("当日板块快照：")
        for row in snap.rows[:12]:
            leader = f"，龙头 {row.leader_stock}" if row.leader_stock else ""
            lines.append(f"- {row.name}：强度{row.strength:.1f}，涨幅{row.change_pct:+.2f}%，主力净额{row.net_flow_yi:+.2f}亿（{row.flow_source}）{leader}")
        self._event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt="\n".join(lines), source_page="板块资金"),
            )
        )
