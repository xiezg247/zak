# vnpy_tickflow

VeighNa **TickFlow 数据源适配**：vnpy `Datafeed` 插件 + 共享客户端与 K 线分页。

## vnpy 加载

`vt_setting.json` 中 `datafeed.name=tickflow` 时，vnpy 懒加载：

```python
from vnpy_tickflow import Datafeed  # TickflowDatafeed 别名
```

## 包结构

```
vnpy_tickflow/
├── client.py      # get_tickflow_client、resolve_tickflow_api_key
├── klines.py      # fetch_klines_paged（分页拉 K 线）
├── mapping.py     # 交易所/周期映射、时间解析
└── datafeed.py    # TickflowDatafeed（VeighNa BaseDatafeed）
```

## 共享 API（供 vnpy_ashare 等调用）

```python
from vnpy_tickflow import get_tickflow_client, fetch_klines_paged, to_tf_symbol

client = get_tickflow_client()
df = fetch_klines_paged(client, "600519.SH", "1m", start_ms, end_ms)
```

API Key 优先级：`get_tickflow_client(api_key=...)` 参数 → 环境变量 `TICKFLOW_API_KEY`；无 Key 时使用 `TickFlow.free()` 日 K 服务。

依赖 `vnpy-common`（`.env` 路径）、`tickflow[all]`。

## 与 vnpy_ashare 的分工

| 模块 | 职责 |
|------|------|
| `vnpy_tickflow` | 客户端、K 线分页、datafeed、符号/时间映射 |
| `vnpy_ashare/quotes/tickflow_client.py` | 实时行情 → `QuoteSnapshot` |
| `vnpy_ashare/quotes/tickflow_stream.py` | WebSocket 流式行情 |
| `vnpy_ashare/data/tickflow_klines.py` | UI 分 K → `BarData` |
