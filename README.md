# 📊 新版商品详情页 A/B 实验分析

电商 APP 新版商品详情页上线前的独立 A/B 实验分析项目。

## 📂 产出物

| 文件 | 说明 |
|------|------|
| [bi_dashboard/dashboard.html](bi_dashboard/dashboard.html) | 交互式 BI 仪表盘（Plotly），双击浏览器打开 |
| [ab_testing_code/product_detail_ab_test.py](ab_testing_code/product_detail_ab_test.py) | 完整实验代码，`np.random.seed(2000)` 结果可复现 |
| [docs/experiment_report.md](docs/experiment_report.md) | 完整分析报告 |
| [docs/experiment_design.md](docs/experiment_design.md) | 实验设计文档与预注册方案 |

## 🚀 快速体验

```bash
# 1. 看仪表盘
双击 bi_dashboard/dashboard.html

# 2. 跑代码（结果与仪表盘、报告完全一致）
python ab_testing_code/product_detail_ab_test.py
```

## 📈 核心结果

| 指标 | 对照组 A | 实验组 B | 提升 | 统计量 | p 值 |
|------|----------|----------|------|--------|------|
| 转化率 | 5.89% | 6.26% | +0.37pp (+6.2%) | Z=2.434 | 0.0149 |
| 人均时长 | — | — | +4.96s | CUPED t=38.0 | <0.001 |
| SRM 卡方 | — | — | — | χ²=0.027 | 0.869 |
| HTE 交互项 | — | — | — | — | 1.10e-06 |

**HTE 分层**：老用户 B-A +0.97pp，新用户 B-A -0.53pp → 建议差异化上线
**CUPED**：协变量 corr=0.525，方差削减 27.9%
**序贯检验**：5 次偷看 α=0.01，全程不显著

## 📊 分析流程

分层随机化 → SRM 卡方检查 → Z 检验 + Welch t 检验 → BH 多重检验校正 → CUPED 方差削减 → HTE 异质性分析 → 序贯检验 α Spending

## 🛠️ 技术栈

- **Python**：NumPy / Pandas / SciPy / StatsModels
- **可视化**：Plotly（交互式仪表盘）
- **统计方法**：Z 检验 / Welch t 检验 / BH 校正 / CUPED / OLS / 序贯检验
- **工具**：Git / Jupyter

© Data-z1
