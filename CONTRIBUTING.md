# 合作说明

1. 首次提交与远程发布由仓库负责人完成；主分支使用 `main`。
2. 从最新 `main` 创建短期分支，如 `feat/rotary-performance` 或 `fix/rotary-edge-case`，不要直接向主分支推送。
3. 保持改动聚焦，提交前运行 `node operators/rotaryposemb/scripts/rotary_regression.cjs`。涉及 NPU 的变更需说明 CANN 版本、硬件、精度及耗时；未运行须明确标注。
4. 提交前检查 `git status --short` 和 `git diff --cached`，不得包含密钥、会话、密码、`.env`、生成数据或构建产物。
5. 提交 PR，说明目的、实现、验证和已知限制，由另一位成员审阅后合并。

官方 `skills/` 默认保留快照；更新时记录来源版本并检查许可及差异。不要为了通过测试修改 golden 或掩盖失败；模板修复须独立 PR，提供可信来源和验证依据。
