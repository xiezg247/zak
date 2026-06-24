"""信息流 normalize 单测。"""

from __future__ import annotations

from vnpy_ashare.integrations.bilibili.normalize import normalize_dynamic


def test_normalize_dynamic_uses_desc_text() -> None:
    draft = normalize_dynamic(
        {
            "id_str": "123456",
            "modules": {
                "module_dynamic": {
                    "desc": {"text": "今天发个动态"},
                    "major": {},
                },
                "module_author": {"pub_ts": 1719000000},
            },
        },
        author_name="测试UP",
    )
    assert draft is not None
    assert draft.external_id == "123456"
    assert draft.item_type == "dynamic"
    assert "今天发个动态" in draft.title


def test_normalize_dynamic_parses_rich_text_nodes() -> None:
    draft = normalize_dynamic(
        {
            "id_str": "999",
            "modules": {
                "module_dynamic": {
                    "desc": {
                        "rich_text_nodes": [
                            {
                                "orig_text": "正文第一段",
                                "text": "正文第一段",
                                "type": "RICH_TEXT_NODE_TYPE_TEXT",
                            },
                            {
                                "orig_text": "第二段",
                                "text": "第二段",
                                "type": "RICH_TEXT_NODE_TYPE_TEXT",
                            },
                        ],
                        "text": "",
                    },
                    "major": None,
                },
                "module_author": {"pub_ts": 1719000000},
            },
        },
        author_name="测试UP",
    )
    assert draft is not None
    assert draft.summary == "正文第一段第二段"
    assert draft.title == "正文第一段第二段"


def test_normalize_dynamic_opus_summary_nodes() -> None:
    draft = normalize_dynamic(
        {
            "id_str": "888",
            "modules": {
                "module_dynamic": {
                    "desc": None,
                    "major": {
                        "opus": {
                            "summary": {
                                "rich_text_nodes": [
                                    {
                                        "orig_text": "图文正文",
                                        "text": "图文正文",
                                        "type": "RICH_TEXT_NODE_TYPE_TEXT",
                                    }
                                ],
                                "text": "",
                            }
                        },
                        "type": "MAJOR_TYPE_OPUS",
                    },
                },
                "module_author": {"pub_ts": 1719000000},
            },
        },
        author_name="测试UP",
    )
    assert draft is not None
    assert draft.summary == "图文正文"
