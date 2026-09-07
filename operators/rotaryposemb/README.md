# RotaryPosEmb 团队算子

题目：https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submit

## 当前结果

2026-09-06，提交 `6a9d8568bf41025d60d073e9` 返回 **Pass**，全部 15 个用例的 `precision_ratio` 均为 `1`。

结果页：https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9d8568bf41025d60d073e9

这是正确性基线，尚未完成性能优化。第 10 例耗时明显高于其他用例。完整返回的时间数值记录在 `RESULTS.md`，这里不推断计分方式或排名。

## 文件

- `kernel.asc`：当前通过评测的实现，保留官方 `run_kernel` 原型。
- `CMakeLists.txt`、`data_utils.h`、`main.asc`、`run.sh`、`scripts/gen_data.py`、`scripts/RotaryPosEmb.py`、`scripts/verify_result.py`：已从官方 authenticated `/package` 解压文件逐字节恢复，保留原始 UTF-8。
- `scripts/rotary_regression.cjs`：CPU 数值与索引回归，不替代 NPU 测试。
- `RESULTS.md`：历史平台评测与 CPU 回归结果。

原工作目录的 `tools/` 未纳入本合作仓库，包括暂缓复制的密码脚本。官方提交工具位于根目录 `skills/cannjudge-submit/`；任何生成的密钥、密码和会话均不得提交。

## 修复说明

逆频率的正确公式为 `1 / theta^(2*i/dim)`。旧版本错误地使用了 `i/dim`，因此除了第一个频率外均与题目不符。之前将 Wrong Answer 归因于 DataCopyPad 或三角函数的结论没有依据；`y=x` 也不是有效的旋转位置编码实现，其评测失败不能证明搬运损坏。

当前 host 仅计算并上传 `dim/2` 个 FP32 逆频率。设备按连续行分工，同一 token 的 head 复用三角函数结果，使用 DataCopyPad 搬运前后两半，FP32 计算旋转，FP16 输出最后舍入。

为满足 A2 Sin/Cos 的值域要求，设备先将已舍入的 FP32 角度减半两次，再用两次倍角公式还原。在 `theta >= 1` 且位置绝对值不超过 `131072` 时，三角函数输入不超过 `32768`。本轮通过的评测不等同于对所有可能参数的证明，特别是 `0 < theta < 1` 的大角度仍需专门验证。

## 验证

CPU 回归：

```powershell
node operators/rotaryposemb/scripts/rotary_regression.cjs
```

本机未进行 CANN 编译或 NPU 验证；上述 Pass 来自历史真实平台评测，不代表恢复后的样例工程已经端到端验证。以下为 CANN 9.0 + NPU 环境的样例入口，当前不保证能够运行：

```bash
cd operators/rotaryposemb
source /usr/local/Ascend/ascend-toolkit/set_env.sh
bash run.sh
```

## 导入编码恢复

此前 `work_rotaryposemb/code/` 文件经 PowerShell 解码保存造成乱码，并非官方 package 原文件损坏。现已从 `C:\Users\12071\AppData\Local\Temp\opencode\pkg\` 将上述 7 个官方支撑文件逐字节复制到相应路径，未重新编码或转换换行；源与目标的字节及 SHA-256 均一致。官方 `scripts/RotaryPosEmb.py` 为正常的 62 行 UTF-8 文本，`inv_freq` 与 `cases` 赋值完整保留。

这是恢复官方原始 golden，不是手动修改 golden 或调整预期结果。通过平台评测的 `kernel.asc`、CPU regression、`RESULTS.md` 与旧 work 目录均未修改。本地仍未进行 CANN 编译或 NPU 验证，详见根目录 `UPSTREAM.md`。

已有评测可通过本页结果链接查看；本次整理没有重新提交或联网查询。
