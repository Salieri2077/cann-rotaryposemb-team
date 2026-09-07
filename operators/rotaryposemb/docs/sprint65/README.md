# 排名冲刺实验记录

目标：按用户2026-09-07的最新要求争取进入排行榜前6。此目录沿用初始的 sprint65 名称。

本轮期间多数测试点的 best_time 变为约0.6，分数无法与此前56.97/65分直接对比。下表基于各结果读取时的 best_time 重算分数，保留逐点原始耗时；不推断隐藏测试shape或硬件时间单位。

| 提交 | 改动 | 结果 | 当时基准分数 |
| --- | --- | --- | ---: |
| [229899](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e8066bf41025d600d023b) | 整行向量旋转、normal整数频率解码、跨token预取 | Pass / 15点 | 10.0521 |
| [230020](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e831abf41025d600e1479) | 多token合并DMA、减少小任务核心数；线上回退 | Pass / 15点 | 9.4675 |
| [230085](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e849dbf41025d600ecd6b) | 双元频率压缩、窄stripe、合并scratch；未超过基线 | Pass / 15点 | 10.0106 |
| [230135](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e8603bf41025d600f407f) | 保留可用核心，合并小任务窗口，按商/余数分配任务；平台脚本TypeError，无有效耗时 | Fail / 15点 | 0.0000 |
| [230173](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e8797bf41025d600fc426) | D64/128特化、精确Axpy约简、扩大安全UB系数批次 | Pass / 15点 | 9.9769 |
| [230270](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e8ac1bf41025d6010e127) | D16/32/64/128轻量参数、低head连续DMA | Pass / 15点 | 10.1801 |
| [230300](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e8c01bf41025d6011483e) | 复用UB，通过Cast/Brcb/Mul向量生成共享角度；线上回退 | Pass / 15点 | 10.0175 |
| [230368](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e8ed2bf41025d60120fc8) | 扩展D256/512轻量参数、恢复原调度；未超过最好版本 | Pass / 15点 | 10.1082 |
| [230446](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e91d2bf41025d6012e595) | D32/64低head编译期分派、共享幂基三角多项式；15点通过但未超过最好版本 | Pass / 15点 | 10.1357 |
| [230524](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e93b7bf41025d60137f15) | 直接FP32取整替代int32往返；15点通过，单独无收益 | Pass / 15点 | 10.0719 |
| [230573](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e94f0bf41025d6013e62c) | 统一34条三角指令的Counter掩码；15点通过，未超过最好版本 | Pass / 15点 | 10.1316 |
| [230620](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e9658bf41025d601462dd) | 低head跨batch输入预取；15点通过，未超过最好版本 | Pass / 15点 | 10.1017 |
| [230660](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e9760bf41025d6014c812) | D32/64低head连续DMA，搬运发射减半；15点通过，未超过最好版本 | Pass / 15点 | 10.1025 |
| [230707](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e98aabf41025d60154433) | theta<1且实际角度有界时复用向量约简；15点通过，未超过最好版本 | Pass / 15点 | 10.1010 |
| [230746](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e99f2bf41025d6015c51c) | 每核单token的小张量入口：紧凑参数、416B存储、显式DMA同步；15点通过，第5名 | Pass / 15点 | 10.4053 |

最终选用提交230746：15/15 Pass，核查时第5名、10.41分，已达到前6目标。小张量入口将第一个测试点从此前最好版本的3.42降至2.99。其余候选保留为实验历史。`experiments.json`关联提交、源码SHA和逐点耗时。未通过性能验证的方案不自动保留在最终源码中。

## 验证范围

- 使用真实kernel代码经透明启动语法适配执行CPU模型，检查数值、队列所有权和地址边界；D64/128特化仍断言每次run仅一次launch。
- host验证从真实Process提取分配语句，覆盖1,812,272种配置、32B核间边界、覆盖范围、UB预算和64位地址。
- 精确Axpy前两段乘积可用FP32精确表示；第三段保留单独乘减。17,000,008角度扫描及8,000,001原始角的位型对比通过。
- 官方7个只读文件保持逐字节一致，未修改golden或校验阈值。
- 本地NumPy power与host powf的107/230项舍入诊断差异仍存在。独立同powf参考通过，最终正确性以实际平台15点结果为准。
- 本地无CANN/NPU，CPU模型不模拟设备异步流水线；每个候选的正式线上计时通常只测一次，微小差异可能含噪声。

## 通用分派约束

所有分派仅基于公开运行时shape、dtype、theta与对齐。频率常量在每次run_kernel内由theta重新生成；未使用输入答案、跨调用缓存、隐藏测试编号或多次kernel启动。
