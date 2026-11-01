# 📊 新版商品详情页 A/B 实验分析

电商 APP 新版商品详情页上线前 A/B 实验全流程分析，包含分层随机化、SRM 检查、Z 检验、BH 多重检验校正、CUPED 方差削减、HTE 异质性分析、序贯检验。

## 📂 产出物

| 文件 | 说明 |
|------|------|
| `bi_dashboard/dashboard.html` | 交互式 BI 仪表盘（Plotly），双击浏览器打开 |
| `ab_testing_code/day7_ab_experiment.py` | 完整实验代码，`np.random.seed(2000)` 结果可复现 |

## 🚀 快速体验

```bash
# 1. 看仪表盘
双击 bi_dashboard/dashboard.html

# 2. 跑代码（结果与仪表盘完全一致）
python ab_testing_code/day7_ab_experiment.py
```

## 📈 核心结果

| 指标 | 对照组 A | 实验组 B | 提升 | 统计量 | p 值 |
|------|---------|---------|------|--------|------|
| 转化率 | 5.89% | 6.26% | +0.37pp (+6.2%) | Z=2.434 | 0.0149 |
| 人均时长 | — | — | +4.96s | CUPED t=38.0 | <0.001 |
| SRM 卡方 | — | — | — | χ²=0.027 | 0.869 |
| HTE 交互项 | — | — | — | — | 1.10e-06 |

**HTE 分层**：老用户 B-A +0.97pp，新用户 B-A -0.53pp → 建议差异化上线

## 🔒 可重复性

`day7_ab_experiment.py` 使用 `np.random.seed(2000)`，仪表盘用同一 seed 生成。README 中每个数值都由脚本自动输出。
