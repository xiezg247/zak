# vnpy_ashare

VeighNa **A 股现货** 图形终端：看盘（自选 / 市场 / 本地）、选股、策略回测与批量对比、AI 上下文与 Service 层。

**不在近期范围**：A 股 Gateway 实盘 / PaperAccount 模拟盘 / Gateway 看盘（远期 P3–P4，见 `docs/roadmap.md`）。

## 在 VeighNa 中加载

```python
from vnpy_ashare import AshareApp

main_engine.add_app(AshareApp)
```

## 独立安装（拆包发布）

将本目录作为 Python 包根目录发布为 `vnpy-ashare`，安装后通过 `import vnpy_ashare` 使用。

自选池与全 A 股列表默认读取 `~/.vntrader/zak.db`；可用 `scripts/export_metadata.py` / `import_metadata.py` 做 CSV 备份。

## 核心模块

| 路径 | 说明 |
|------|------|
| `launcher.py` | GUI 启动 |
| `services/` | 6 个业务 Service |
| `screener/` | 选股因子 / 规则 / 方案 |
| `ui/quotes/` | 看盘页 controller 拆分 |
| `ui/batch_backtest_flow.py` | 批量回测流程 |
| `ai/context_store.py` | 终端 AI 共享内存态 |
| `bar_health.py` | 本地 K 线健康检测 |

完整文档见仓库 [docs/README.md](../docs/README.md)。
