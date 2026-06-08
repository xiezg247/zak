# vnpy_ashare

VeighNa A 股行情应用，提供 **市场 / 自选 / 本地** 三个 App。

## 在 VeighNa 中加载

```python
from vnpy_ashare import AshareApp

main_engine.add_app(AshareApp)
```

## 独立安装（拆包发布）

将本目录作为 Python 包根目录发布为 `vnpy-ashare`，安装后通过 `import vnpy_ashare` 使用。

自选池与全 A 股列表默认读取 `~/.vntrader/zak.db`；可用 `scripts/export_metadata.py` / `import_metadata.py` 做 CSV 备份。

核心模块：`launcher`（GUI 启动）、`paths`（路径）、`config`（A 股常量）、`models`（StockItem）、`bars`（K 线下载）、`app_db`（元数据库）、`universe`（全市场同步）。

元数据库默认路径：`~/.vntrader/zak.db`。UI 在 `ui/`（`main_window`、`quotes_page`、`fonts` 等）。
