# RotaryPosEmb 团队合作项目

汇集团队的 RotaryPosEmb 算子正确性基线与官方 Skills - CANNBot，供分支开发和 PR 协作。

目标 GitHub 仓库：https://github.com/Salieri2077/cann-rotaryposemb-team.git

本仓库采用独立 Git 历史，不包含官方仓库的原始 `.git` 或本机登录信息。

## 目录

- `operators/rotaryposemb/`：完整算子代码、CPU regression、平台结果与使用说明。
- `skills/`：官方完整 Skills - CANNBot 快照，包括官方提交工具、模板和示例。
- `UPSTREAM.md`：官方来源、精确版本、复制边界与已知问题。
- `TEAM_SUBMISSIONS.md`：队友 swlaird 的可见提交记录；当前算子已纳入其提交 224901 的源码与验证工具。
- `LICENSE`、`Third_Party_Open_Source_Software_Notice`：原样保留的官方许可及第三方声明。

## 验证

在本仓库根目录运行：

```sh
node operators/rotaryposemb/scripts/rotary_regression.cjs
```

此回归仅验证 CPU 数值与索引模型，不替代 CANN 编译或 NPU 评测。当前提交 224901 的平台记录为 15/15 Pass、记录得分 43.58，详见 [结果](operators/rotaryposemb/RESULTS.md)。7 个支撑文件已用官方 authenticated `/package` 解压文件逐字节恢复为原始 UTF-8，修复此前 PowerShell 解码保存造成的导入乱码，不是手动修改 golden。本地尚未进行 CANN 编译或 NPU 验证，不能将 `run.sh` 视为已验证可运行，详见 [算子说明](operators/rotaryposemb/README.md)。

## 安全与许可

仅纳入经过选择的算子验证和打包工具；未包含原工作目录的认证客户端、登录会话、密钥或诊断探针。官方脚本保留不代表其生成的凭据可以提交；运行后须检查 `git status` 和暂存差异。

官方内容适用 **CANN Open Software License Agreement Version 2.0**，不是 MIT。保留各文件版权和第三方声明，使用及分发限制以原始许可文本为准。合作流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
