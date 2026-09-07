# 上游与迁移记录

## 官方来源

- 官方地址：https://gitcode.com/cann/cann-learning-hub.git
- 本地官方仓库 `git rev-parse HEAD`：`1bac4c6f3ef7165037ccd0ef39a56ae0b8f2b1a7`
- 整理日期：2026-09-07。
- 许可：**CANN Open Software License Agreement Version 2.0**，不是 MIT；完整文本见根 `LICENSE`。
- 第三方声明：根 `Third_Party_Open_Source_Software_Notice`。

版本记录来自本地 Git，不表示已联网核验远程最新版本。`skills/` 及两个许可文件逐字节复制，与本地源文件完全一致。核对该 HEAD 的 Git blob 时，65 个文件中有 51 个仅存在工作区 CRLF 与 HEAD LF 的差异；仅在内存比较时归一化换行后内容完全一致，没有重新编码或改写副本。根 `.gitattributes` 指定后续 Git 文本入库及检出使用 LF，当前复制文件保留原始字节。

## 明确白名单

- 官方 `skills/` 完整内容复制至 `skills/`，保留其自带脚本和示例图片。
- 官方根 `LICENSE`、`Third_Party_Open_Source_Software_Notice` 原样保留。
- 初始从 `work_rotaryposemb/code/` 完整复制至 `operators/rotaryposemb/`；随后按下述记录从官方 package 恢复 7 个支撑文件。通过平台评测的 `kernel.asc` 与 CPU regression 保持不变。
- `work_rotaryposemb/RESULTS.md` 原样保留至算子目录；`README.md` 保留结果和技术说明，适配新路径并补充已知问题。
- 新增根 README、协作说明、忽略规则、LF 属性和本来源记录。

不复制源 `.git`、任何密钥或会话、`work_rotaryposemb/tools/`（含暂缓纳入的应用工具密码脚本）、其他本地工具凭据、`work_probe_passthrough/` 或白名单外内容。独立仓库的 `.git` 由本地 `git init` 新建，不继承官方仓库历史或配置。

## 导入编码恢复与验证边界

2026-09-07，根据已确认的官方 authenticated `/package` 解压文件恢复导入编码。源目录为 `C:\Users\12071\AppData\Local\Temp\opencode\pkg\`，目标为 `operators/rotaryposemb/`。先验证源、目标及其 `scripts/` 路径，再用 `Copy-Item` 逐字节复制以下白名单，不进行文本解码保存或换行转换：

- `CMakeLists.txt`
- `data_utils.h`
- `main.asc`
- `run.sh`
- `scripts/gen_data.py`
- `scripts/RotaryPosEmb.py`
- `scripts/verify_result.py`

7 个目标文件与官方解压源文件逐字节及 SHA-256 比对一致，均通过严格 UTF-8 解码检查。官方 `scripts/RotaryPosEmb.py` 为正常的 62 行文本；此前乱码及赋值被吞进注释的问题来自 `work_rotaryposemb/code/` 经 PowerShell 解码保存的导入过程，并非官方 package 原文件损坏。本次是恢复官方原始 UTF-8 与 golden，不是手动修改 golden 或调整预期结果。

未复制 package 的 `kernel.asc`。算子目录中通过平台评测的 `kernel.asc`、`scripts/rotary_regression.cjs` 和 `RESULTS.md` 的复制前后 SHA-256 均未变化；旧 work 目录未修改。本地尚未进行 CANN 编译或 NPU 验证，CPU regression 与历史平台 15/15 Pass 不代表恢复后的 `run.sh` 或样例工程已通过端到端验证。

GitHub 目标仓库由用户创建：https://github.com/Salieri2077/cann-rotaryposemb-team.git 。后续提交和推送仅在独立合作仓库中进行，不修改原官方仓库的 origin。
