---
name: tdx-risk-analysis
description: 单票风险分析。通过 analyze_risk 工具获取波动率、回撤、Beta、行业风险、市场情绪。
author: zak
version: 1.0.0
---

# tdx-risk-analysis

单票风险分析 Skill，数据来自 zak 终端内置的 `AnalysisService.analyze_risk`，基于本地 K 线计算风险指标。

## 适用场景

- "风险怎么样"
- "波动大不大"
- "回撤多少"
- 团队分析模式中的风险维度

## 调用方式

```
analyze_risk(symbol="600519.SSE")
```

## 返回维度

- **价格风险**：年化波动率、最大回撤、下行标准差
- **系统性风险**：Beta、与大盘相关性
- **流动性风险**：日均成交额、换手率
- **行业风险**：所属行业近期表现

## 注意事项

- 数据来源：本地 K 线计算
- 需要至少 60 根日 K 线才能计算有效指标
- K 线不足时 `data_availability` 相关字段为 false
