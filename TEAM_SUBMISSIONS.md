# 小组可见提交记录

来源：当前账号可访问的 CANNJudge 赛事提交列表，按用户提供的队友昵称 `swlaird` 查询。初始查询返回 5 条记录，后续优化记录见下文。下列时间保留平台 UTC 格式。

| 提交时间（UTC） | 状态 | 提交 |
| --- | --- | --- |
| 2026-09-06 18:31:44 | Pass | [6a9db190bf41025d60db0a29](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9db190bf41025d60db0a29) |
| 2026-09-06 18:21:45 | Runtime Error | [6a9daf39bf41025d60da9a50](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9daf39bf41025d60da9a50) |
| 2026-09-06 18:05:28 | Compile Error | [6a9dab68bf41025d60d9cdcd](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9dab68bf41025d60d9cdcd) |
| 2026-09-06 18:02:14 | Compile Error | [6a9daaa6bf41025d60d9a7fd](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9daaa6bf41025d60d9a7fd) |
| 2026-09-06 17:15:46 | Runtime Error | [6a9d9fc2bf41025d60d77f36](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9d9fc2bf41025d60d77f36) |

初始记录只包含平台可见元数据。现已由 swlaird 提供提交 224901 的完整源码，作为最初基线纳入 operators/rotaryposemb/kernel.asc，并补齐 CPU 验证工具；详情见算子 README 和 RESULTS。

本仓库此前的算子基线对应另一条通过记录（保留历史）：
[6a9d8568bf41025d60d073e9](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9d8568bf41025d60d073e9)，15 个用例均为 Pass、precision_ratio=1，详见 [RESULTS.md](operators/rotaryposemb/RESULTS.md)。

上一轮性能优化采用提交 **229648**，15/15 Pass，记录得分 **56.97**。[结果](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e7a73bf41025d600acdfa)；[逐轮对比](operators/rotaryposemb/docs/optimization/README.md)。



## 排名冲刺更新

当前纳入提交 **230746**：15/15 Pass，本轮基准 **10.41**。[评测](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e99f2bf41025d6015c51c)；[实验及逐点耗时](operators/rotaryposemb/docs/sprint65/README.md)。2026-09-07核查时第5名，达到前6目标，旧计分基准不可直接比较。
