"""申万 2021 行业分类与成分（index_classify / index_member_all）。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from vnpy_ashare.domain.symbols.stock import ts_code_to_vt_symbol
from vnpy_ashare.integrations.tushare.cache import (
    DATASET_SW2021_CLASSIFY,
    DATASET_SW2021_MEMBER,
    INDUSTRY_MAX_AGE,
    get_cached_l2_to_l1_map,
    get_cached_rows,
    get_cached_sw_industry_l1_map,
    get_cached_sw_industry_map,
    set_cached_l2_to_l1_map,
    set_cached_rows,
    set_cached_sw_industry_l1_map,
    set_cached_sw_industry_map,
)
from vnpy_ashare.integrations.tushare.client import get_tushare_pro

SwIndustryLevel = Literal["L1", "L2", "L3"]
SW_INDUSTRY_SRC = "SW2021"
_DEFAULT_INDUSTRY_LEVEL: SwIndustryLevel = "L2"

_CLASSIFY_FIELDS = "index_code,industry_name,level,industry_code,is_pub,parent_code,src"
_MEMBER_FIELDS = "ts_code,name,l1_code,l1_name,l2_code,l2_name,l3_code,l3_name,in_date,out_date,is_new"


def _frame_records(frame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    return [dict(record) for record in frame.to_dict(orient="records")]


def fetch_sw_classify(*, level: SwIndustryLevel = "L2") -> list[dict[str, Any]]:
    """拉取申万行业分类列表。"""
    pro = get_tushare_pro()
    try:
        frame = pro.index_classify(level=level, src=SW_INDUSTRY_SRC, fields=_CLASSIFY_FIELDS)
    except Exception:
        return []
    return _frame_records(frame)


def fetch_sw_member_rows() -> list[dict[str, Any]]:
    """拉取申万 2021 全量行业成分（含 L1/L2/L3）。"""
    pro = get_tushare_pro()
    try:
        frame = pro.index_member_all(is_new="Y", fields=_MEMBER_FIELDS)
    except Exception:
        return []
    return _frame_records(frame)


def _is_active_member(row: dict[str, Any]) -> bool:
    out_date = str(row.get("out_date") or "").strip()
    return not out_date


def _industry_name_for_level(row: dict[str, Any], level: SwIndustryLevel) -> str:
    if level == "L1":
        return str(row.get("l1_name") or "").strip()
    if level == "L3":
        name = str(row.get("l3_name") or "").strip()
        if name:
            return name
    name = str(row.get("l2_name") or "").strip()
    if name:
        return name
    return str(row.get("l1_name") or "").strip()


def member_rows_to_industry_map(
    rows: list[dict[str, Any]],
    *,
    level: SwIndustryLevel = _DEFAULT_INDUSTRY_LEVEL,
) -> dict[str, str]:
    """成分行 → ts_code 行业名（默认 L2）。"""
    mapping: dict[str, str] = {}
    for row in rows:
        if not _is_active_member(row):
            continue
        ts_code = str(row.get("ts_code") or "").strip()
        industry = _industry_name_for_level(row, level)
        if ts_code and industry:
            mapping[ts_code] = industry
    return mapping


def member_rows_to_l2_parent_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    """成分行 → 申万 L2 名 → L1 名。"""
    mapping: dict[str, str] = {}
    for row in rows:
        if not _is_active_member(row):
            continue
        l2 = str(row.get("l2_name") or "").strip()
        l1 = str(row.get("l1_name") or "").strip()
        if l2 and l1:
            mapping[l2] = l1
    return mapping


def build_grouped_l2_industries(
    l2_names: Sequence[str],
    l2_to_l1: Mapping[str, str],
) -> list[tuple[str, list[str]]]:
    """L2 行业名按申万 L1 分组，返回 [(L1, [L2...]), ...]。"""
    groups: dict[str, list[str]] = defaultdict(list)
    orphans: list[str] = []
    for l2 in l2_names:
        cleaned = str(l2).strip()
        if not cleaned:
            continue
        l1 = str(l2_to_l1.get(cleaned) or "").strip()
        if l1:
            groups[l1].append(cleaned)
        else:
            orphans.append(cleaned)
    result = [(l1, sorted(l2_list)) for l1, l2_list in sorted(groups.items())]
    if orphans:
        result.append(("", sorted(orphans)))
    return result


def format_industry_filter_label(l2: str, l1: str | None = None) -> str:
    """行业筛选下拉展示文案（L1 / L2）。"""
    cleaned_l2 = str(l2).strip()
    cleaned_l1 = str(l1 or "").strip()
    if cleaned_l1:
        return f"{cleaned_l1} / {cleaned_l2}"
    return cleaned_l2


def get_sw_classify_rows(*, level: SwIndustryLevel = "L2", max_age=INDUSTRY_MAX_AGE) -> list[dict[str, Any]] | None:
    return get_cached_rows(f"{DATASET_SW2021_CLASSIFY}_{level}", "", max_age=max_age)


def classify_rows_to_l2_index_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    """申万 L2 行业名 → index_code。"""
    mapping: dict[str, str] = {}
    for row in rows:
        name = str(row.get("industry_name") or "").strip()
        code = str(row.get("index_code") or "").strip()
        if name and code:
            mapping[name] = code
    return mapping


def build_sw_l2_board_definitions(
    *,
    classify_rows: list[dict[str, Any]] | None = None,
    member_rows: list[dict[str, Any]] | None = None,
    l2_to_l1: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """申万 2021 L2 行业板块定义（index_code / name / l1_name / member_count）。"""
    classify = classify_rows if classify_rows is not None else (get_sw_classify_rows(level="L2") or [])
    members = member_rows if member_rows is not None else (get_sw_member_rows() or [])
    parent_map = dict(l2_to_l1) if l2_to_l1 is not None else (get_cached_l2_to_l1_map() or {})

    member_counts: dict[str, int] = defaultdict(int)
    for row in members:
        if not _is_active_member(row):
            continue
        l2 = str(row.get("l2_name") or "").strip()
        if l2:
            member_counts[l2] += 1

    boards: list[dict[str, Any]] = []
    for row in classify:
        name = str(row.get("industry_name") or "").strip()
        index_code = str(row.get("index_code") or "").strip()
        if not name or not index_code:
            continue
        boards.append(
            {
                "index_code": index_code,
                "name": name,
                "l1_name": str(parent_map.get(name) or "").strip(),
                "member_count": member_counts.get(name, 0),
            }
        )
    return sorted(boards, key=lambda item: str(item["name"]))


def fetch_sw_l2_member_count_map(*, force: bool = False) -> dict[str, int]:
    """申万 L2 名 → 当前有效成分股数量。"""
    members = get_sw_member_rows()
    if not members:
        sync_sw_industry_snapshot(force=force)
        members = get_sw_member_rows() or []
    counts: dict[str, int] = defaultdict(int)
    for row in members:
        if not _is_active_member(row):
            continue
        l2 = str(row.get("l2_name") or "").strip()
        if l2:
            counts[l2] += 1
    return dict(counts)


def fetch_sw_l2_index_map(*, force: bool = False) -> dict[str, str]:
    """申万 L2 名 → index_code。"""
    if not force:
        classify = get_sw_classify_rows(level="L2")
        if classify:
            return classify_rows_to_l2_index_map(classify)
    sync_sw_industry_snapshot(force=force)
    classify = get_sw_classify_rows(level="L2") or []
    return classify_rows_to_l2_index_map(classify)


def member_rows_vt_symbols_for_l2(l2_name: str, *, member_rows: list[dict[str, Any]] | None = None) -> set[str]:
    """申万 L2 行业成分 → vt_symbol 集合。"""
    target = str(l2_name or "").strip()
    if not target:
        return set()
    rows = member_rows if member_rows is not None else (get_sw_member_rows() or [])
    symbols: set[str] = set()
    for row in rows:
        if not _is_active_member(row):
            continue
        if str(row.get("l2_name") or "").strip() != target:
            continue
        ts_code = str(row.get("ts_code") or "").strip()
        vt_symbol = ts_code_to_vt_symbol(ts_code)
        if vt_symbol:
            symbols.add(vt_symbol)
    return symbols


def sync_sw_industry_snapshot(*, force: bool = False) -> tuple[dict[str, str], int]:
    """拉取申万成分并写入本地缓存；返回 (L2 映射, 条数)。"""
    if not force:
        cached = get_cached_sw_industry_map()
        if cached:
            return cached, len(cached)

    for level in ("L1", "L2", "L3"):
        classify_rows = fetch_sw_classify(level=level)
        if classify_rows:
            set_cached_rows(f"{DATASET_SW2021_CLASSIFY}_{level}", "", classify_rows)

    member_rows = fetch_sw_member_rows()
    if not member_rows:
        return {}, 0

    set_cached_rows(DATASET_SW2021_MEMBER, "", member_rows)
    l2_mapping = member_rows_to_industry_map(member_rows, level=_DEFAULT_INDUSTRY_LEVEL)
    l1_mapping = member_rows_to_industry_map(member_rows, level="L1")
    l2_to_l1 = member_rows_to_l2_parent_map(member_rows)
    if l2_mapping:
        set_cached_sw_industry_map(l2_mapping)
    if l1_mapping:
        set_cached_sw_industry_l1_map(l1_mapping)
    if l2_to_l1:
        set_cached_l2_to_l1_map(l2_to_l1)
    return l2_mapping, len(l2_mapping)


def fetch_sw_industry_l1_map(*, force: bool = False) -> dict[str, str]:
    """ts_code → 申万 L1 行业名。"""
    if not force:
        cached = get_cached_sw_industry_l1_map()
        if cached:
            return cached
    members = get_sw_member_rows()
    if members:
        return member_rows_to_industry_map(members, level="L1")
    if force:
        sync_sw_industry_snapshot(force=True)
        return get_cached_sw_industry_l1_map() or {}
    return {}


def fetch_l2_to_l1_map(*, force: bool = False) -> dict[str, str]:
    """申万 L2 名 → L1 名。"""
    if not force:
        cached = get_cached_l2_to_l1_map()
        if cached:
            return cached
    members = get_sw_member_rows()
    if members:
        return member_rows_to_l2_parent_map(members)
    if force:
        sync_sw_industry_snapshot(force=True)
        return get_cached_l2_to_l1_map() or {}
    return {}


def fetch_sw_industry_map(*, force: bool = False) -> dict[str, str]:
    """ts_code → 申万 L2 行业名；无缓存时尝试拉取。"""
    if not force:
        cached = get_cached_sw_industry_map()
        if cached:
            return cached
    mapping, _count = sync_sw_industry_snapshot(force=force)
    return mapping


def get_sw_member_rows(*, max_age=INDUSTRY_MAX_AGE) -> list[dict[str, Any]] | None:
    return get_cached_rows(DATASET_SW2021_MEMBER, "", max_age=max_age)
