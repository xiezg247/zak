"""vnpy_mcp 与工具能力状态测试。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from vnpy_llm.tools.status import build_tools_status
from vnpy_mcp.app.engine import McpEngine
from vnpy_mcp.config.registry import BUILTIN_MCP_PROVIDERS
from vnpy_mcp.config.settings import DEFAULT_TDX_MCP_URL, McpServerConfig, load_all_mcp_servers, load_mcp_dir
from vnpy_mcp.domain.provider import McpToolInfo
from vnpy_mcp.remote.provider import RemoteMcpProvider
from vnpy_skills.app.engine import SkillEngine


@contextmanager
def _mcp_dir(*files: tuple[str, dict]):
    with tempfile.TemporaryDirectory() as tmp:
        mcp_dir = Path(tmp) / "mcp"
        mcp_dir.mkdir()
        for name, content in files:
            (mcp_dir / name).write_text(json.dumps(content), encoding="utf-8")
        with patch.dict(os.environ, {"MCP_DIR": str(mcp_dir)}, clear=False):
            yield mcp_dir


@contextmanager
def _empty_mcp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        mcp_dir = Path(tmp) / "mcp"
        mcp_dir.mkdir()
        with patch.dict(os.environ, {"MCP_DIR": str(mcp_dir)}, clear=False):
            yield mcp_dir


class McpConfigTests(unittest.TestCase):
    def test_load_mcp_json_multi_servers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mcp_dir = Path(tmp) / "mcp"
            mcp_dir.mkdir()
            (mcp_dir / "mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "tdx": {
                                "url": DEFAULT_TDX_MCP_URL,
                                "headers": {"tdx-api-key": "secret-key"},
                            },
                            "data": {
                                "url": "https://example.com/mcp",
                                "headers": {"Authorization": "Bearer token"},
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            configs = load_mcp_dir(mcp_dir)
            self.assertIn("tdx", configs)
            self.assertIn("data", configs)
            self.assertTrue(configs["tdx"].available)

    def test_config_priority_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mcp_dir = root / "mcp"
            mcp_dir.mkdir()
            legacy = root / "mcp.json"
            legacy.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "tdx": {
                                "url": "https://legacy.example/mcp",
                                "headers": {"tdx-api-key": "l"},
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            (mcp_dir / "mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "tdx": {
                                "url": "https://local.example/mcp",
                                "headers": {"tdx-api-key": "m"},
                            },
                            "extra": {"url": "https://extra.example/mcp"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            configs = load_all_mcp_servers(
                mcp_dir=mcp_dir,
                extra_paths=[legacy, mcp_dir / "mcp.json"],
            )
            self.assertEqual(configs["tdx"].url, "https://local.example/mcp")
            self.assertEqual(configs["extra"].url, "https://extra.example/mcp")

    def test_single_file_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mcp_dir = Path(tmp) / "mcp"
            mcp_dir.mkdir()
            (mcp_dir / "mcp.json").write_text(
                json.dumps({"mcpServers": {"tdx": {"url": "https://base.example/mcp"}}}),
                encoding="utf-8",
            )
            (mcp_dir / "tdx.json").write_text(
                json.dumps({"url": "https://override.example/mcp", "headers": {"tdx-api-key": "k"}}),
                encoding="utf-8",
            )
            configs = load_mcp_dir(mcp_dir)
            self.assertEqual(configs["tdx"].url, "https://override.example/mcp")
            self.assertTrue(configs["tdx"].available)

    def test_remote_provider_uses_config(self) -> None:
        provider = RemoteMcpProvider(
            McpServerConfig(
                name="tdx",
                url=DEFAULT_TDX_MCP_URL,
                headers={"tdx-api-key": "secret-key"},
            )
        )
        self.assertTrue(provider.available)


class McpEngineTests(unittest.TestCase):
    def test_tool_prefix(self) -> None:
        with _mcp_dir(("mcp.json", {"mcpServers": {"tdx": {"url": DEFAULT_TDX_MCP_URL, "headers": {"tdx-api-key": "k"}}}})):
            engine = McpEngine()
            engine.load_all()
            provider = engine.providers["tdx"]
            self.assertEqual(provider.prefixed_name("stock_quotes"), "mcp_tdx_stock_quotes")

    def test_internal_status_note_connected(self) -> None:
        with _mcp_dir(("mcp.json", {"mcpServers": {"tdx": {"url": DEFAULT_TDX_MCP_URL, "headers": {"tdx-api-key": "k"}}}})):
            engine = McpEngine()
            engine.load_all()
            with patch("vnpy_mcp.app.engine.list_remote_tools", return_value=[McpToolInfo(name="wenda", description="")]):
                engine.init_providers()
            note = engine.build_internal_status_note()
            self.assertIn("已连接", note)
            self.assertIn("diagnose_stock", note)
            self.assertNotIn("mcp_tdx_wenda", note)

    def test_builtin_placeholder_when_missing_file(self) -> None:
        with _empty_mcp_dir():
            engine = McpEngine()
            engine.load_all()
            provider = engine.providers["tdx"]
            self.assertFalse(provider.available)
            self.assertIn("mcp/mcp.json", provider.missing_env[0])

    @patch("vnpy_mcp.app.engine.list_remote_tools")
    def test_init_with_mock_tools(self, mock_list: unittest.mock.MagicMock) -> None:
        mock_list.return_value = [McpToolInfo(name="stock_quotes", description="个股报价")]
        with _mcp_dir(
            (
                "mcp.json",
                {
                    "mcpServers": {
                        "tdx": {
                            "url": DEFAULT_TDX_MCP_URL,
                            "headers": {"tdx-api-key": "test-key"},
                        }
                    }
                },
            )
        ):
            engine = McpEngine()
            engine.load_all()
            enabled = engine.init_providers()
        self.assertIn("tdx", enabled)
        self.assertEqual(len(engine.get_tool_specs()), 1)

    @patch("vnpy_mcp.app.engine.list_remote_tools")
    def test_multiple_servers(self, mock_list: unittest.mock.MagicMock) -> None:
        mock_list.return_value = [McpToolInfo(name="tool_a", description="A")]
        with _mcp_dir(
            (
                "mcp.json",
                {
                    "mcpServers": {
                        "tdx": {
                            "url": "https://a.example/mcp",
                            "headers": {"tdx-api-key": "k1"},
                        },
                        "data": {
                            "url": "https://b.example/mcp",
                            "headers": {"Authorization": "k2"},
                        },
                    }
                },
            )
        ):
            engine = McpEngine()
            engine.load_all()
            enabled = engine.init_providers()
        self.assertEqual(set(enabled), {"tdx", "data"})

    @patch("vnpy_mcp.app.engine.list_remote_tools")
    def test_ensure_providers_lazy_connect(self, mock_list: unittest.mock.MagicMock) -> None:
        mock_list.return_value = [McpToolInfo(name="stock_quotes", description="个股报价")]
        with _mcp_dir(
            (
                "mcp.json",
                {
                    "mcpServers": {
                        "tdx": {
                            "url": DEFAULT_TDX_MCP_URL,
                            "headers": {"tdx-api-key": "test-key"},
                        }
                    }
                },
            )
        ):
            engine = McpEngine()
            engine.load_all()
            self.assertFalse(engine.providers_initialized)
            enabled = engine.ensure_providers()
            self.assertTrue(engine.providers_initialized)
            self.assertIn("tdx", enabled)
            mock_list.assert_called_once()
            engine.ensure_providers()
            mock_list.assert_called_once()

    def test_skip_unconfigured(self) -> None:
        with _empty_mcp_dir():
            engine = McpEngine()
            engine.load_all()
            enabled = engine.init_providers()
        self.assertEqual(enabled, [])


class ToolsStatusTests(unittest.TestCase):
    @patch("vnpy_mcp.app.engine.list_remote_tools")
    def test_build_snapshot(self, mock_list: unittest.mock.MagicMock) -> None:
        mock_list.return_value = [McpToolInfo(name="stock_quotes", description="个股报价")]
        with _mcp_dir(
            (
                "mcp.json",
                {
                    "mcpServers": {
                        "tdx": {
                            "url": DEFAULT_TDX_MCP_URL,
                            "headers": {"tdx-api-key": "test-key"},
                        }
                    }
                },
            )
        ):
            skill_engine = SkillEngine()
            skill_engine.load_all()
            skill_engine.init_skills()
            mcp_engine = McpEngine()
            mcp_engine.load_all()
            mcp_engine.init_providers()
            snapshot = build_tools_status(skill_engine, mcp_engine)

        self.assertTrue(any(item.name == "tdx" for item in snapshot.mcps))
        self.assertIn("MCP", snapshot.compact_summary())

    def test_build_snapshot_idle_before_connect(self) -> None:
        with _mcp_dir(
            (
                "mcp.json",
                {
                    "mcpServers": {
                        "tdx": {
                            "url": DEFAULT_TDX_MCP_URL,
                            "headers": {"tdx-api-key": "test-key"},
                        }
                    }
                },
            )
        ):
            skill_engine = SkillEngine()
            skill_engine.load_all()
            skill_engine.init_skills()
            mcp_engine = McpEngine()
            mcp_engine.load_all()
            snapshot = build_tools_status(skill_engine, mcp_engine)

        tdx = next(item for item in snapshot.mcps if item.name == "tdx")
        self.assertEqual(tdx.state, "idle")
        self.assertNotIn("待配置", snapshot.compact_summary())


class RegistryTests(unittest.TestCase):
    def test_builtin_meta(self) -> None:
        self.assertIn("tdx", BUILTIN_MCP_PROVIDERS)
        self.assertIn("通达信", BUILTIN_MCP_PROVIDERS["tdx"].title)


if __name__ == "__main__":
    unittest.main()
