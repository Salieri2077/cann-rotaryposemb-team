# 流水线、内存布局与数学改写实验

2026-09-07 至 2026-09-08（Asia/Shanghai）。本轮仅比较自身耗时，不使用排名或 best_time。最终保留 positions 单缓存直接同步版，源码 SHA-256 `1b772e01fa7c7e1c7e22ea4f79c4b052d553ffe1b5e3cc17f2d6e0c0a9e56bb8`，两次正式评测均 15/15 Pass，所有 precision_ratio=1。

当前已保留的组合、已确认现象、源码疑点及下一轮验收方法见[瓶颈记录](BOTTLENECKS.md)。

## 保留结果与测量边界

原版 A1=[233123](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9ed64ec76b321ca6a7913e)、A2=[233505](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9edf1fc76b321ca6aac11d)，候选 P1=[233235](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9ed8e9c76b321ca6a892ea)、P2=[233563](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9ee06fc76b321ca6ab38e6)。原版源码来自 main 的 `cc254e4614501bf625e23390854779c6cd8b780b`，SHA-256 `3616b92cf7c5ed62916ebbd0432756192816b5081d20af72bbcf5e4c1bbc2c26`。两次原版提交与两次候选提交各自源码完全相同。

先对每个测试点的两轮耗时取算术平均，再计算 15 个“候选/原版”耗时比的几何平均，其下降为 **3.00%**。分开按 P1/A1、P2/A2 计算分别下降 **4.15%**、**1.82%**。全部测试耗时之和下降 **0.37%**，因为第 10 点占主要耗时且基本未改善。

只有各两次提交，不构成统计显著性结论。A2 相对 A1 自身快了 2.12%，第 1 点代码完全未改却有波动；不能把所有逐点变化归因于代码。后续改动应继续在相邻时段复测原版与候选。

| 测试点 | 原版两轮均值 / μs | 新版两轮均值 / μs | 耗时下降 |
| --- | ---: | ---: | ---: |
| 1 | 2.990 | 2.985 | 0.17% |
| 2 | 5.575 | 5.375 | 3.59% |
| 3 | 9.340 | 8.575 | 8.19% |
| 4 | 17.855 | 17.365 | 2.74% |
| 5 | 20.590 | 20.085 | 2.45% |
| 6 | 32.240 | 31.220 | 3.16% |
| 7 | 30.050 | 29.455 | 1.98% |
| 8 | 17.505 | 16.305 | 6.86% |
| 9 | 46.630 | 44.960 | 3.58% |
| 10 | 6500.015 | 6497.490 | 0.04% |
| 11 | 47.460 | 45.535 | 4.06% |
| 12 | 60.200 | 58.255 | 3.23% |
| 13 | 351.400 | 345.830 | 1.59% |
| 14 | 870.040 | 864.780 | 0.60% |
| 15 | 296.640 | 289.695 | 2.34% |

## 实现与同步

原实现将只由 Scalar 读取的 positions 放在 VECIN TQue 中，经历 AllocTensor、EnQue、DeQue、FreeTensor，之后仍需 MTE2_S 才能安全 GetValue。保留版改为相同大小的 256B TBuf，缓存仍然一次最多读取 64 个 int32，命中及填充策略不变。

- 缓存首次填充或重新填充后：DataCopyPad → MTE2_S Set/Wait → Scalar GetValue。
- 复用同一缓存前：S_MTE2 Set/Wait，保证旧值的 Scalar 读取完成后 MTE2 才覆盖。
- 事件即时成对，缓存生命周期由 TPipe 管理。输入/输出原有双缓冲不变，UB 用量不增加，最大分配仍为 192800B。
- Tiny 路径、数学运算、host 分派、频率生成及所有设备入口逐字节不变。

减少不必要的 Vector 依赖是收益的合理解释；本机没有 NPU profiler，尚未用流水线轨迹验证具体停顿减少了多少。

## 六个独立候选

以下均真实提交 NPU，且 15/15 Pass。下表仅是初筛的一轮测量，不应将小于原版自身波动的差异当作确定收益。单缓存另有上述复测。

| 独立方案 | 提交 | 相对 A1 的耗时比几何平均下降 |
| --- | --- | ---: |
| 角度缓冲区错开 UB bank | [233178](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9ed796c76b321ca6a81ce9) | 1.01% |
| positions 单缓存直接同步（保留） | [233235](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9ed8e9c76b321ca6a892ea) | 4.15% |
| π/2 约简及更低阶联合 sin/cos | [233281](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9eda2dc76b321ca6a8fb7c) | -0.65% |
| Payne–Hanek 只计算所需整数乘积窗口 | [233319](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9edb59c76b321ca6a96296) | 0.40% |
| positions 双缓存预取流水线 | [233386](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9edca3c76b321ca6a9e1ea) | 1.82% |
| 单缓存增加 256B 空间对照 | [233440](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9edddec76b321ca6aa4b1a) | 1.44% |

双缓存相对单缓存 P1 慢 2.43%。它提前搬下一批 positions，增加一份 256B 缓存和事件管理，但此次没有抵消其成本；增加 256B 而不预取的对照也没有优于 P1。该对照仍只有一轮，无法精确分离 UB 地址变化、控制开销和噪声的贡献。

π/2 方案降低多项式阶数，但本轮耗时略回退。象限重建、依赖链或调度成本可能抵消了潜在收益，具体原因尚未通过 profiler 核实。整数乘积窗口方案将大角度约简的宽乘积缩小，CPU 精度扫描通过，但第 10 点的 NPU 耗时未显著改变，不能据此认定大角度约简就是该点瓶颈。UB bank 调整只有约 1% 的单轮变化，低于已观察到的原版漂移。这些方案均不进入最终内核。

扩大普通约简范围到 196608 的方案仅做了本地数值验证，未在 NPU 上测试，也未纳入最终版本。组合方案也没有 NPU 结果，本报告不声称它们有效。

## 复现与验证

[results.json](results.json) 保存经过筛选的正式提交元数据、源码散列及逐点原始结果；不包含账号会话、排名或凭据。[validation.json](validation.json) 记录本地检查规模。运行 `python3 summarize.py` 可重算上述双轮指标。

本轮最终代码通过 998 个实际源码模型用例、1191 个小张量专项用例（含与原版逐位比较）、11160 组基础回归、11 个入口 C++14 语法检查、10 项工具测试。模型新增 S_MTE2 事件计数和总 Set/Wait 配对检查，保持 Tiny 的 18 项统计 ABI。模型是同步执行，不能证明真实设备时序、事件 ID 竞争或性能。最终编译、精度依据为两次平台 15/15 Pass。

NumPy 2.4.4 power 与 host powf 舍入不同的既有 107/230 项诊断差异继续保留；同 powf 独立参考通过。没有修改 golden 或精度阈值。7 个官方只读文件保持逐字节一致。

CANN 9.0.0，目标 dav-2201；具体评测硬件型号未独立报告。平台元数据 iterations=5，但统计聚合方式及 host/device 计时范围未独立核实。μs 单位依据[官方前端 testcaseTimeLabel](https://cannjudge.cn/js/ui/shared.js)；不把该字段称作纯设备耗时。

各 `.patch` 都独立基于上述原版 SHA，不应叠加应用。可在原版临时目录中 `git apply <方案>.patch`，随后核对 results.json 对应源码 SHA。range.patch 对应本地候选 SHA `6a586be8fe86771f64ea54414c44c535f358b34922fb1429b9898b6cea9eae92`，没有正式提交结果。

后续最值得解决的是第 10 点：先在匹配的 NPU 上分别测完整内核、搬运/旋转路径与角度生成路径，获取流水线及向量利用率，再选择优化方向。独立 microbenchmark 只用于本地归因，不替代完整算子的正式结果。
