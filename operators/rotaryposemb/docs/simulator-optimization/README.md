# 根据 CANN 仿真与线上复测优化批处理

2026-09-08。本轮从源码 SHA `1b772e01fa7c7e1c7e22ea4f79c4b052d553ffe1b5e3cc17f2d6e0c0a9e56bb8` 出发，只比较自身耗时。正式候选为 `batch8guard4`，SHA `64ea1e92ea94220ea61a349df194864fc4948ad802e2b0b1eb73035a9c369085`。

## 正式提交与两轮复测

最终同一源码两轮为 [242827](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6aa002c6c76b321ca6054ab5) 和 [243107](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6aa0092fc76b321ca607befd)，均 **15/15 Pass，precision_ratio=1**。对照为同一基线的 242391 / 243044。先对每个点的两次耗时取几何平均，再计算 15 个候选/基线比值的几何平均，本轮下降 **1.91%**。该指标不是排行榜分数。

| 指标 | 基线 A2 / A3 | 保留版 G1 / G2 |
|---|---:|---:|
| 第 6 点 / μs | 32.06 / 31.64 | 23.39 / 23.77 |
| 第 10 点 / μs | 6500.44 / 6499.53 | 6501.08 / 6503.54 |

第 6 点两轮几何均值下降 **25.97%**，四种候选/基线配对均更快。整体只约 1.9%，因为其余点多数没有明显变化，部分有所回退，第 10 点仍未改善。A3/A2 基线自身 GMR 变化约 +0.075%，但只有各两轮且提交间隔并不完全相邻，不能据此推导统计置信区间或保证后续加速。

完整逐点结果、候选筛选与漂移见 [线上复核](online_comparison.md)。[提交回执](submission_receipts.json)保存 POST 使用的源码 SHA、字节数与返回的提交 ID；[online/](online/)仅含经过筛选的我方结果，不含会话或凭据。运行 `python review_online.py` 可从这些文件重算；G1/G2 的平均不混入不同源码的 J1。

## 实现与取舍

原先 H>4 一律使用共享系数、逐 token 旋转的路径。现在当 **5≤H≤8、token 数不少于可用核数、角度缓冲可容纳至少 4 个完整 token**，且仍满足原有 32B 输出对齐条件时，复用已有的批处理路径，把多个 token 的搬运、系数广播和旋转合并。它只修改 host 的分派条件，设备计算、频率生成、数学公式、事件和缓冲分配代码均不变；H≤4 保持原分派。

容量条件是 `maxBatch=floor(2048/(H×RowStride))≥4`。它表示容量，不保证实际每批为 4：最终批大小仍由核数、数据量和对齐约束共同决定。H=8 时新增范围止于 D128，D256/512 继续使用原共享路径。

逐步筛选的依据：

- 直接扩大到 H≤8，在单核 H8/D64/257 tokens 上把模拟时长从 75.01 降到 42.69 μs，但 H8/D512 从 15.39 增到 17.46 μs。
- 加入容量门槛后，D512 恢复到 15.39 μs。token 数门槛则保留小输入原先的跨 head 分核机会。新增分支中的批大小不会超过原共享路径的 tokenGrain，因此不会减少该分支的实际核数；这不代表所有输入都能满核。
- 更窄的 `batch8guard4multi` 还要求 `tokens>workPartitions`，用来排除实际 batch=1。它是性能对照，不是正确性修复。尽管 batch=1 的新路径有更多源级 DMA/Vector 调用，32 核模拟却从 4.39 降到 3.75 μs，不能凭调用数认定退步。

## 模拟器结果与测量边界

使用官方 CANN 9.0.0 Toolkit、bisheng、`-O2 -g -std=c++17 --npu-arch=dav-2201`，通过 CAModel 与 `msopprof simulator --soc-version=Ascend910B1` 实际执行完整内核。本地没有实体 NPU。以下是 profiler 的 `duration_time(us)`；多核取最慢核，不能视作 CANNJudge 的整点实卡耗时。

| 人工样例，FP32，theta=10000 | 请求核数 | 基线 / μs | batch8guard4 / μs | 缩短 |
|---|---:|---:|---:|---:|
| N257/H8/D64 | 1 | 75.01 | 42.69 | 43.09% |
| N257/H8/D64 | 32 | 7.11 | 6.28 | 11.67% |
| N257/H8/D128 | 32 | 7.41 | 6.80 | 8.23% |
| N32/H8/D64 | 32 | 4.39 | 3.75 | 14.58% |

N=B×S。这些是公开合约内自行构造的参数族，并非平台隐藏测试的复现。每次执行用新输出目录、校验输入与源码 SHA，并检查 same-powf 和官方 NumPy 两份参考。输入/输出、完整 trace 与日志保存在本地实验目录；仓库只保存紧凑报告与可复现工具。

## 其他已实现并筛选的方向

所有补丁都独立基于上述基线，**不可依次叠加**；源码 SHA 见 [candidates.json](candidates.json)。补丁使用零行上下文，在精确基线上执行 `git apply --unidiff-zero <candidate>.patch`；12 份补丁均实际应用并核对了结果 SHA。

| 候选 | 完整内核模拟观察 | 保留判断 |
|---|---|---|
| pipeline：先完成 positions 读取再发 x 搬运 | 低 H 长样例 25.91→21.91 μs | 线上未证实整体改善，留作独立实验 |
| math：根据实际最大 position 与频率选择安全约简 | 小 theta 样例 9.01→4.18 μs | 线上接近持平；不加入正式组合 |
| padding：PH 只处理真实维度 | 非对齐小 theta 样例 9.01→8.49 μs | 仅模拟验证 |
| broadcast：减少局部张量句柄构造 | 长低 H 样例 25.91→25.67 μs | 收益很小 |
| anglehandle：缓存整个角度区句柄 | 长低 H 样例 25.91→26.84 μs | 退步，弃用 |
| fixedwide：D256/512/1024 固定维度入口 | 三例分别约缩短 21%/8.5%/5% | 线上未证实收益；不加入正式组合 |
| theta1：每 token 仅计算一对三角系数再广播 | 两例 14.30→15.23、23.62→26.07 μs | 单独减少数学计算反而更慢 |
| theta1init：再跳过已经无用的频率初始化 | 同两例降至 12.72、15.40 μs | 线上 15/15，但未证实加速；不加入正式组合 |

theta1init 只用于 theta 恰为 1、D≥256 且半行无 padding 的输入，保持原多项式与 FP32 角度语义；没有用近似递推生成频率。其控制标记与 math 候选冲突，不能直接叠加补丁。

## 瓶颈认识的更新

1. **已在模型中确认一种流水等待。** 低 H 路径原先发 x DMA 后再取 position，导致 Scalar 等待。pipeline 候选把同一长样例的批次 MTE2→Scalar 等待从约 4.357 降至 0.004 μs，Vector 与 MTE2 的非同步在途区间交集从约 2.233 增至 4.471 μs。见 [逐指令分析](pipeline-trace.md)。这解释局部模拟收益，但线上未出现对应整体收益。
2. **中等 H 的逐 token 调用存在合并空间。** 批处理对已知 D64/128 参数族有效，容量不足时广播与重复 trig 的成本会反超。不能用一个统一的 H 阈值覆盖所有 D。
3. **少算数学不等于完整内核更快。** theta1 的额外 Scalar↔Vector 同步和扩展成本抵消了短多项式收益，省掉频率初始化后才获益。应同时看初始化、同步、广播及主体计算。
4. **第 10 点仍未定位。** 整点约 6500 μs，主要候选没有明显改变它；shape/theta 和硬件 pipe profile 未公开。不能把人工 theta<1 或宽 D 样例直接当作第 10 点。
5. **下一步优先匹配实卡参数族。** 获取已知 shape 的实卡完整内核 profile，关注每核工作量、工作单元之间的空隙、有效读写带宽与宽 D 初始化。人工微基准只能帮助归因，不能替代完整题意的提交。

流水区间可能重叠；上述交集不是 PMU 利用率，不能把各 pipe 时长相加当作总时长分摊。CPU 模型中的 API 次数也不是硬件指令数。

## 正确性与已知参考差异

正式候选通过实际源码 CPU 的 230 项 same-powf 用例、47 项批处理定向逐位对照、96 项 UB/边界用例、1,812,272 种实际 host 分块配置、11 个 CPU stub 入口语法检查，以及 11,160 组基础代数/地址回归。C++14 stub 检查不能替代真实 CANN 编译；真实工具链使用 C++17。核函数参数布局不变，仍满足 1536B 上限，7 个官方只读文件保持一致。

原有 NumPy power 与 host powf 舍入差异仍未解决：CPU 全套中 107/230 项严格 NumPy 诊断不通过，same-powf 参考全部通过。新增 D1024/theta=0.5/position=64 模拟用例也暴露了这项基线问题：baseline 与 combo 都通过 same-powf，但官方 NumPy 不一致比例约 0.00163，超过本地阈值。失败记录保留，未修改 golden 或放宽精度要求。平台 15/15 通过只证明平台本次测试覆盖的正确性。

工具依据：[官方性能调优指南](https://asc.gitcode.com/guide/programming_guide/debug_and_tuning/performance_tuning.html)、[msopprof simulator 文档](https://github.com/Ascend/msopprof/blob/master/docs/en/user_guide/msopprof_simulator_user_guide.md)。
