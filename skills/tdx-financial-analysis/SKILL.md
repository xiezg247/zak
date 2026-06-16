---
name: tdx-financial-analysis
description: 单票财务深度分析。通过 analyze_financial 工具获取盈利能力、成长性、估值、偿债能力。
author: zak
version: 1.0.0
---

# tdx-financial-analysis

单票财务深度分析 Skill，数据来自 zak 终端内置的 `AnalyzeService.analyze_financial`，后续接入 Tushare 财务接口补全详细指标。

## 适用场景

- "财务面怎么样"
- "PE ROE 如何"
- "盈利质量好不好"
- 团队分析模式中的财务维度

## 调用方式

```
analyze_financial(symbol="600519.SSE")
```

## 返回维度

- **估值**：PE(TTM)、PB、PS（后续补全）
- **盈利能力**：ROE、毛利率、净利率、扣非净利润同比
- **成长性**：营收/利润 CAGR（近 3 年）
- **偿债能力**：资产负债率、流动比率

## 注意事项

- 数据来源：Tushare 财务接口（需配置 Tushare Token）
- 返回值包含 `data_availability` 标记各维度数据是否可用
- 数据缺失时如实说明，禁止编造
