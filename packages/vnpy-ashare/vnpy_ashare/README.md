# vnpy_ashare

VeighNa **A 股现货** 图形终端：看盘、策略选股、自动选股、回测、AI 上下文与 Service 层。

## 在 VeighNa 中加载

```python
from vnpy_ashare import AshareApp

main_engine.add_app(AshareApp)
```

## 核心模块

| 路径 | 说明 |
|------|------|
| `launcher.py` | GUI 启动 |
| `services/` | 7 个业务 Service |
| `screener/` | 选股因子 / 规则 / 方案 / 配方 / 标杆对标 |
| `ui/quotes/` | 看盘页 controller 拆分 |
| `ui/auto_screener_page.py` | 自动选股页 |
| `ui/batch_backtest_flow.py` | 批量回测流程 |
| `ai/context_store.py` | 终端 AI 共享内存态 |
| `bar_health.py` | 本地 K 线健康检测 |

元数据默认在 `~/.vntrader/zak.db`；CSV 备份见 `scripts/export_metadata.py`。

完整文档见 [docs/README.md](../docs/README.md)。
