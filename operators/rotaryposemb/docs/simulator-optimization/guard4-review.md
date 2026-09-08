# guard4 / guard4multi 独立代码审查

审查日期：2026-09-08。仅核对实际源文件与已有报告；本次审查未修改内核、未运行 CAModel、未提交平台。

**结论：guard4 可以保留为实测候选，没有发现新增的正确性或合规阻断。multi 是另一项性能筛选，不能凭 API 数量认定更优。** 最终选择仍由相同源码复测和基线漂移决定。

| 版本 | 源码 | SHA-256 |
|---|---|---|
| baseline | `/data7/chenyundan/files/code/cann-lab/9.0.0/rope-sim/kernel.asc` | `1b772e01fa7c7e1c7e22ea4f79c4b052d553ffe1b5e3cc17f2d6e0c0a9e56bb8` |
| guard4 | `/tmp/rope-opt-batch8-guard4/kernel.asc` | `64ea1e92ea94220ea61a349df194864fc4948ad802e2b0b1eb73035a9c369085` |
| multi | `/tmp/rope-opt-batch8-guard4multi/kernel.asc` | `e90f1f0279b41f429a7f687ed09fbfeffd7288bfd0412af2d431ae2af16cc625` |

两者相对 baseline 均只改变 `run_kernel` 主机分派表达式。guard4 在原 H≤4 条件之外加入 H≤8、tokens≥cores、maxBatch≥4，并保留原有 maxBatch≥tokenAlignment 条件；multi 再要求 tokens>workPartitions。新增范围实际是 H=5–8。

| 检查项 | 结论与实际代码证据 |
|---|---|
| 跨核 32B 输出边界 | [tokenAlignment 与批次取整](/tmp/rope-opt-batch8-guard4/kernel.asc:1323)保证 batchTokens 是 `32/gcd(H*D*sizeof(T),32)` 的倍数。[核间划分](/tmp/rope-opt-batch8-guard4/kernel.asc:459)以完整 work unit 划分，所以每核首 token 对应字节地址对齐。尾批只写真实 token 数；[CopyOut](/tmp/rope-opt-batch8-guard4/kernel.asc:670)写真实半行长度，不把 UB padding 作为有效输出。 |
| 核数退化 | tokens≥cores 排除原 [跨 head 分核](/tmp/rope-opt-batch8-guard4/kernel.asc:1345)所需的 tokens<cores 区间。新增范围原先均为 groups=1，且 maxBatch≥4 推出 H*rowStride≤512，原路径也用 2048 I/O tile。新 batch 上限是 2048/(H*rowStride)，不大于原 tokenGrain 的容量上限 2048/rowStride；同一目标粒度及对齐后的 batchTokens≤原 tokenGrain，所以新 workUnits 与 blockCount 不会更小。这不保证所有输入满核。 |
| UB | [初始化](/tmp/rope-opt-batch8-guard4/kernel.asc:385)公式不变；batchTokens*H*rowStride≤2048。[完整预算枚举](/tmp/rope-opt-batch8-guard4/boundary_budget.json)覆盖 H=5–8、两种 dtype、偶数 D16–1024，共 4040 配置，其中 520 个满足容量与对齐条件。新增分支显式 TPipe 分配最大 **131616 B＜196608 B**，multi 是其子集。 |
| 行数与 repeat | 批次最多 256 行；DMA blockCount 使用 uint16_t。[连续批次](/tmp/rope-opt-batch8-guard4/kernel.asc:859)的 D16 路径每 repeat 覆盖 8 行，D128 路径最多 32 行，所以 uint8_t repeat 不会溢出。[ContiguousBatch](/tmp/rope-opt-batch8-guard4/kernel.asc:640)把 D16 非完整 stripe 尾部转回通用路径。 |
| 广播别名与同步 | [ExpandTokenTrig](/tmp/rope-opt-batch8-guard4/kernel.asc:1005)每阶段的目标从 `ceil(pending/H)*H` 开始，不覆盖阶段内仍需读取的 compact 源；阶段之间有 Vector barrier。token0 跳过自身 head0，避免单条 Copy 的源目的重叠。该论证适用于 H=5–8；headCount≤8 可装入 uint8_t。 |
| 整数范围 | [输入约束](/tmp/rope-opt-batch8-guard4/kernel.asc:1291)限制 N≤1048576、H≤256、D≤1024；workPartitions≤131070，32 位的 ceil/div、H*rowStride、H*D*typeBytes 均安全。输入总字节与 GM 行偏移先在 uint64_t 中计算。本次新增的比较条件未引入新的乘积或窄化。 |
| 旧行为与比赛合规 | H≤4 条件的逻辑值保持不变，H≥9 与 Tiny 也保持不变。数学函数、搬运、同步代码字节不变。新增选择只依赖 shape、dtype、可用核数；未加入隐藏 case 编号、答案数据、跨次缓存或额外启动。按用户提供的禁止词表扫描，两份候选均未匹配相关标识符。 |

`maxBatch≥4` 是容量门槛，**不是实际 batchTokens≥4**。multi 的 `tokens>workPartitions` 主要排除完整批次大小为 1 的情况，实际批次仍可能为 2，尾批仍可为 1。这是性能假设，并非安全修复。

根任务报告的 N32/H8/D64/32 核 CAModel 观测为 baseline 4.39→guard4 3.75 μs、数值通过，已构成“batch1 必然退步”的反例；这是仿真局部观测，不能当作实卡普遍收益。原先 D512 的回退由 maxBatch≥4 条件排除。审查没有理由仅凭 batch1 API 次数而排除 guard4。

已有验证报告：guard4 定向 CPU 47/47、multi 51/51 与 baseline 输出逐位一致，实际捕获分派配置和选中路径的 18 项计数吻合。multi 的原 230 项 same-powf 检查通过，原有 107 项 NumPy 诊断差异仍存在，不能表述成全部参考通过。这些是同步 CPU 证据，不单独证明异步 NPU 行为。guard4 线上 G1 已完整 15/15 Pass；线上效果由独立统计报告保留，不写入静态正确性结论。

尚需决定的事项：同源码 G1/G2 与 A2/A3 比较，确认局部改善可重复且其他点没有不可接受回退；J1/multi 单独评价。公开资料未提供其他隐藏点 shape 与完整 testcase_id 映射，不能从时长反推某点的 H/D。
