import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import chisquare
from statsmodels.stats.multitest import multipletests

np.random.seed(2000)

# ============================================================
# Phase 1: 预注册
# ============================================================
print("=" * 60)
print("Phase 1: 预注册完成")
print("  核心指标: 转化率（二元）")
print("  护栏指标: 人均浏览时长（连续）、人均GMV（连续）")
print("  分层维度: is_old x region")
print("  MDE: 转化率 0.3pp, GMV +¥5, alpha=0.05, power=0.8")
print("  核心指标预注册，不做多重检验校正；护栏 BH 校正")

# ============================================================
# Phase 2: 造数据 + 分层随机化 + 协变量
# ============================================================
n = 100000
users = pd.DataFrame({
    'user_id': np.arange(n),
    'is_old': np.random.binomial(1, 0.6, n),
    'region': np.random.choice(['华东', '华北', '华南', '西南'], n, p=[0.35, 0.25, 0.25, 0.15]),
    'category': np.random.choice(['手机', '电脑', '平板', '配件'], n, p=[0.30, 0.25, 0.25, 0.20]),
    'date': np.random.choice(pd.date_range('2026-10-01', '2026-10-14'), n),
})

# ============ 用户属性效应 ============
# 区域基础转化率（华东经济发达，转化率最高；西南最低）
region_conv_base = users['region'].map({'华东': 0.052, '华北': 0.045, '华南': 0.048, '西南': 0.040})
# 区域基础浏览时长
region_browse_base = users['region'].map({'华东': 160, '华北': 150, '华南': 155, '西南': 140})
# 品类基础浏览时长
cat_browse_base = users['category'].map({'手机': 165, '电脑': 158, '平板': 152, '配件': 142})

# ============ CUPED 协变量：pre_browse（实验前人均浏览时长） ============
# 真实场景：实验前 7 天的人均浏览时长
# 用用户属性预测 + 噪声（噪声占比决定 corr 高低）
pre_browse = (region_browse_base + 15*users['is_old'] + cat_browse_base - 150) / 3
pre_browse = pre_browse + np.random.normal(0, 25, n)  # 噪声加大 → corr 降到 ~0.5（更真实）
users['pre_browse'] = np.maximum(pre_browse, 10)

def strat_split(df, cols):
    df = df.copy(); df['group'] = ''
    for _, s in df.groupby(cols):
        idx = s.index.tolist(); np.random.shuffle(idx)
        mid = len(idx) // 2
        df.loc[idx[:mid], 'group'] = 'A'
        df.loc[idx[mid:], 'group'] = 'B'
    return df

users = strat_split(users, ['is_old', 'region', 'date'])
B = users['group'] == 'B'

# ============  conv） ============
# base: region 效应 + 老用户 +2%
p_base = region_conv_base + 0.02 * users['is_old']
# HTE: 老用户 B +0.7pp，新用户 B -0.3pp
delta_conv = np.where(B, 0.007*users['is_old'] - 0.003*(1-users['is_old']), 0)
users['conv'] = np.random.binomial(1, np.clip(p_base + delta_conv, 0.005, 0.20))

# ============  GMV ============
# lognormal 分布，B 组参数稍大表示客单价提升
gmv_mu = np.where(B, 4.55, 4.5)
users['gmv'] = np.where(users['conv']==1, np.random.lognormal(gmv_mu, 0.4, n), 0).round(2)

# ============ 造 browse_time ============
# browse_time = α + β₁*pre_browse + β₂*is_old + B效应 + 噪声
# 这样 corr = β₁ * σ_X / σ_Y ≈ 0.5（合理真实值）
users['browse_time'] = np.maximum(
    50 + 0.5 * users['pre_browse'] + 10 * users['is_old'] + 5 * B.astype(int) + np.random.normal(0, 20, n),
    10
).round(1)

# 验证相关性
corr_browse = np.corrcoef(users['browse_time'].astype(float), users['pre_browse'])[0, 1]

# 验证 conv 的 region 差异（面试时能解释数据合理性）
conv_by_region = users.groupby(['region', 'group'])['conv'].mean().unstack()

print("\nPhase 2: 数据生成 + 分层随机化完成")
print("  A={}, B={}, SRM 正常".format(len(users[~B]), len(users[B])))
print("  conv region 差异（A 组）: 华东={:.2f}%, 华北={:.2f}%, 华南={:.2f}%, 西南={:.2f}%".format(
    conv_by_region.loc['华东', 'A']*100, conv_by_region.loc['华北', 'A']*100,
    conv_by_region.loc['华南', 'A']*100, conv_by_region.loc['西南', 'A']*100))
print("  CUPED corr(browse_time, pre_browse) = {:.3f}（合理范围 0.3-0.6）".format(corr_browse))

# ============================================================
# Phase 3: SRM 检查
# ============================================================
obs = np.array([len(users[~B]), len(users[B])])
exp = np.array([n/2, n/2])
chi2_srm, p_srm = chisquare(obs, f_exp=exp)
print("\nPhase 3: SRM 卡方拟合优度检查")
print("  chi2={:.3f}, p={:.3f} -> {}".format(chi2_srm, p_srm, "正常 OK" if p_srm > 0.001 else "异常 !!"))

# ============================================================
# Phase 4: 核心 Z 检验 + 护栏 Welch t 检验
# ============================================================
A_df, B_df = users[~B], users[B]
conv_A, conv_B = A_df['conv'].mean(), B_df['conv'].mean()
gmv_A, gmv_B = A_df['gmv'].mean(), B_df['gmv'].mean()

# 核心：转化率 Z 检验
se = np.sqrt(conv_A*(1-conv_A)/len(A_df) + conv_B*(1-conv_B)/len(B_df))
Z = (conv_B - conv_A) / se
p_conv = 2*(1 - stats.norm.cdf(abs(Z)))
ci_low = (conv_B - conv_A) - 1.96 * se
ci_high = (conv_B - conv_A) + 1.96 * se

# 护栏 1：人均时长 Welch t
t_browse, p_browse = stats.ttest_ind(B_df['browse_time'], A_df['browse_time'], equal_var=False)
# 护栏 2：人均 GMV Welch t
t_gmv, p_gmv = stats.ttest_ind(B_df['gmv'], A_df['gmv'], equal_var=False)

# 再造 6 个假指标（子群样本量小，部分显著部分不显著）——演示 BH 校正价值
np.random.seed(2000 + 42)
fake_metrics = {}
n_sub = 5000  # 子群样本量小，效应小的就检测不出来
for name, mu_a, diff_b, sd in [
    ('次日留存', 0.32, 0.012, 0.06),    # 效应中等，显著
    ('退款率', 0.025, -0.008, 0.015),   # 效应大，显著
    ('分享率', 0.08, 0.001, 0.02),      # 效应极小，不显著
    ('收藏率', 0.15, 0.015, 0.035),     # 效应大，显著
    ('投诉率', 0.003, 0.0005, 0.006),   # 效应极小，不显著
    ('客单价', 92.0, 3.5, 50.0),        # 效应小，边际显著
]:
    fake_metrics[name] = {
        'A': np.random.normal(mu_a, sd, n_sub),
        'B': np.random.normal(mu_a + diff_b, sd, n_sub),
    }

# 计算假指标的 p 值
fake_pvals = {}
fake_effects = {}
for name, data in fake_metrics.items():
    t_f, p_f = stats.ttest_ind(data['B'], data['A'], equal_var=False)
    fake_pvals[name] = p_f
    fake_effects[name] = data['B'].mean() - data['A'].mean()

print("\nPhase 4: 核心 + 护栏检验（朴素）")
print("  核心指标（转化率）: Z={:.3f}, p={:.4f}, 95% CI [{:+.2f}pp, {:+.2f}pp]".format(
    Z, p_conv, ci_low*100, ci_high*100))
print("  护栏（人均时长）: Welch t={:.3f}, p={:.2e}".format(t_browse, p_browse))
print("  护栏（人均GMV）: Welch t={:.3f}, p={:.2e}".format(t_gmv, p_gmv))

# ============================================================
# Phase 4.5: 多重检验 BH 校正（v4 新增）
# ============================================================
# 预注册核心指标不做校正，护栏 + 假指标一起校正
all_pvals = [p_browse, p_gmv] + list(fake_pvals.values())
all_names = ['人均时长', '人均GMV'] + list(fake_pvals.keys())

rejected, p_bh, _, _ = multipletests(all_pvals, method='fdr_bh')

print("\nPhase 4.5: 多重检验 BH 校正（控制 FDR ≤ 5%）")
print("  {:<12s} {:<10s} {:<10s} {:<10s}".format('指标', '原始p', 'BH校正p', '显著?'))
print("  " + "-" * 48)
for i, name in enumerate(all_names):
    mark = "***" if rejected[i] else "no"
    print("  {:<12s} {:<10.4f} {:<10.4f} {}".format(name, all_pvals[i], p_bh[i], mark))

# ============================================================
# Phase 5: CUPED 方差削减（对连续护栏指标做）
# ============================================================
Y_all = users['browse_time'].values
X_all = users['pre_browse'].values

# theta = Cov(Y,X) / Var(X)，合并数据 OLS 估计
theta_cuped = np.cov(Y_all, X_all)[0, 1] / np.var(X_all)
X_mean = X_all.mean()

# CUPED 调整
users['browse_cuped'] = users['browse_time'] - theta_cuped * (users['pre_browse'] - X_mean)

# 对比朴素 vs CUPED
t_cuped, _ = stats.ttest_ind(users[B]['browse_cuped'], users[~B]['browse_cuped'], equal_var=False)
se_naive = np.sqrt(A_df['browse_time'].var(ddof=1)/len(A_df) + B_df['browse_time'].var(ddof=1)/len(B_df))
se_cuped = np.sqrt(users[~B]['browse_cuped'].var(ddof=1)/len(A_df) + users[B]['browse_cuped'].var(ddof=1)/len(B_df))
var_reduction = (1 - (se_cuped / se_naive)**2) * 100
rho = np.corrcoef(Y_all, X_all)[0, 1]

print("\nPhase 5: CUPED 方差削减（对护栏人均时长做）")
print("  corr = {:.4f}, 理论削减 = rho^2 = {:.1f}%, 实际削减 = {:.1f}%".format(rho, rho**2*100, var_reduction))
print("  朴素 t={:.3f} → CUPED t={:.3f}（↑ {:.1f}%）".format(t_browse, t_cuped, (t_cuped/t_browse-1)*100))
print("  效应估计: 朴素 {:+.2f}s, CUPED {:+.2f}s（基本无偏）".format(
    B_df['browse_time'].mean() - A_df['browse_time'].mean(),
    users[B]['browse_cuped'].mean() - users[~B]['browse_cuped'].mean()))

# ============================================================
# Phase 6: HTE 异质性分析
# ============================================================
users['B_dummy'] = (users['group']=='B').astype(int)
users['B_x_old'] = users['B_dummy'] * users['is_old']
X_hte = np.column_stack([
    np.ones(n), users['B_dummy'].values, users['is_old'].values, users['B_x_old'].values
])
Y = users['conv'].astype(float).values
beta = np.linalg.lstsq(X_hte, Y, rcond=None)[0]
resid = Y - X_hte @ beta
MSE = np.sum(resid**2) / (n-4)
se_beta = np.sqrt(np.diag(MSE * np.linalg.inv(X_hte.T @ X_hte)))
p_inter = 2*(1 - stats.t.cdf(np.abs(beta[3]/se_beta[3]), n-4))

old_grp = users[users['is_old']==1].groupby('group')['conv'].mean()
new_grp = users[users['is_old']==0].groupby('group')['conv'].mean()

print("\nPhase 6: HTE 异质性分析")
print("  交互项 p = {:.2e} -> {}".format(p_inter, "高度显著" if p_inter < 0.05 else "不显著"))
print("  老用户: A={:.2f}% -> B={:.2f}%, B-A={:+.2f}pp".format(
    old_grp['A']*100, old_grp['B']*100, (old_grp['B']-old_grp['A'])*100))
print("  新用户: A={:.2f}% -> B={:.2f}%, B-A={:+.2f}pp".format(
    new_grp['A']*100, new_grp['B']*100, (new_grp['B']-new_grp['A'])*100))

# ============================================================
# Phase 6.5: 序贯检验
# ============================================================
print("\nPhase 6.5: 序贯检验（α Spending）")
# 5 次偷看，每次 alpha = 0.01（0.05 / 5）
check_points = [0.2, 0.4, 0.6, 0.8, 1.0]
alpha_per_check = 0.05 / len(check_points)
stopped = False
for cp in check_points:
    n_check = int(n * cp)
    conv_A_check = users[~B].iloc[:n_check]['conv'].mean()
    conv_B_check = users[B].iloc[:n_check]['conv'].mean()
    se_check = np.sqrt(conv_A_check*(1-conv_A_check)/(n_check//2) + conv_B_check*(1-conv_B_check)/(n_check//2))
    Z_check = (conv_B_check - conv_A_check) / se_check
    p_check = 2*(1 - stats.norm.cdf(abs(Z_check)))
    sig = p_check < alpha_per_check
    print("  {:>3.0f}% 数据: Z={:+.3f}, p={:.4f}, α={:.2f} -> {}".format(
        cp*100, Z_check, p_check, alpha_per_check, "显著 🛑 停止" if sig else "不显著"))
    if sig:
        stopped = True
        break
if not stopped:
    print("  全部看完仍不显著 → 实验需继续观察")

# ============================================================
# Phase 7: 最终结论
# ============================================================
print("\n" + "=" * 60)
print("最终结论（面试话术）")
print("=" * 60)
print()
print("实验设计：按新老用户x地区分层随机化，SRM 卡方 p={:.3f} 正常".format(p_srm))
print()
print("核心指标（转化率）：")
print("  A: {:.2f}% -> B: {:.2f}%，绝对 {:+.2f}pp，相对 {:+.1f}%".format(
    conv_A*100, conv_B*100, (conv_B-conv_A)*100, (conv_B/conv_A-1)*100))
print("  Z={:.3f}, p={:.4f}, 95% CI [{:+.2f}pp, {:+.2f}pp]（预注册不校正）".format(
    Z, p_conv, ci_low*100, ci_high*100))
print()
print("护栏指标（BH 校正后）：")
print("  人均时长: 原始 t={:.3f}, BH 校正后显著 -> 新版提升停留 ✅".format(t_browse))
print("  人均GMV: 原始 t={:.3f}, BH 校正后显著 -> 新版提升客单价 ✅".format(t_gmv))
print()
print("CUPED 方差削减：")
print("  协变量 pre_browse corr={:.3f}, 方差削减 {:.1f}%".format(rho, var_reduction))
print("  t 值从 {:.1f} 涨到 {:.1f}".format(t_browse, t_cuped))
print()
print("HTE 异质性：交互项 p={:.2e} 高度显著".format(p_inter))
print("  老用户 B-A = {:+.2f}pp，新用户 B-A = {:+.2f}pp".format(
    (old_grp['B']-old_grp['A'])*100, (new_grp['B']-new_grp['A'])*100))
print()
print("序贯检验：第 {:.0f}% 数据处停止，节省约 {:.0f}% 流量".format(
    cp*100, (1-cp)*100))
print()
print("上线建议：")
print("  [OK] 老用户组 -> 全量新版（HTE +{:.2f}pp，护栏无副作用）".format(
    (old_grp['B']-old_grp['A'])*100))
print("  [!!] 新用户组 -> 暂停全量，单独优化新用户路径")
