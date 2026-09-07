# RotaryPosEmb 团队算子

当前内核为 swlaird 的提交 **224901**，平台 **15/15 Pass**，记录得分 **43.58**。
[评测结果](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9db190bf41025d60db0a29)。
完整逐点记录见 [RESULTS.md](RESULTS.md) 和 [原始结果摘要](docs/submission_224901.json)。

## 实现

- 保留官方 run_kernel 签名与 FP16/FP32 输入，按前后半维配对，FP32 中间计算。
- H 较大时同 token 跨 head 共享三角函数；H 较小时批处理 token，结合双缓冲和自适应多核分块。
- 非对齐行使用 DataCopyPad，按完整 32B 边界分配跨核输出，使用 64 位 GM 偏移。
- theta>=1 使用三段 2π 约减；theta<1 使用整数 Payne–Hanek 约减。
- 每次调用恰好启动一个核函数，核参数总计 1472B，静态断言限制为 1536B。
- 小维度直接传 FP32 频率；大维度用每三项一个起点、两个 int16 位型残差无损编码，host/device 使用相同整数 FP32 乘法预测，恢复原始频率位型。无额外 GM 频率表分配或拷贝。
- 提交源码不包含调试打印。打包前检查平台已知禁用标识符；该检查不等同于完整平台审核规则。

7 个官方支撑文件与原仓库逐字节一致，golden 没有修改。原队友版本保留在 Git 历史，其评测记录保留于 RESULTS.md。

## CPU 检查

在仓库根目录执行；Python 脚本需要 NumPy，实际内核模型与分块检查还需要 g++：

~~~bash
node operators/rotaryposemb/scripts/rotary_regression.cjs
python3 -m unittest discover -s operators/rotaryposemb/tests -p 'test_*.py'
python3 operators/rotaryposemb/tests/test_host_tiling.py
python3 operators/rotaryposemb/tests/run_cpu_kernel.py
python3 operators/rotaryposemb/tools/check_template.py
~~~

现有 Node 回归保留用于旧版算法与索引模型；新增 Python/C++ 模型执行当前 kernel.asc 的实际主体，检查索引、搬运边界、队列容量、数值结果和每次恰好一次启动。CPU 模型使用 CPU sin/cos 和模拟 scratch，不能替代 CANN 编译、异步流水及性能验证。

与相同 host powf 频率的独立参考相比，230/230 用例通过；分块检查覆盖 1,812,272 种配置。本机 NumPy 2.4.4 的 SIMD power 舍入与 host powf 存在差异，230 例中 107 例超过本地严格阈值；该诊断单独报告，未改 golden 或放宽阈值。本次真实平台 15 个测试点全部通过。

## NPU 验证与打包

目标环境：CANN 9.0、dav-2201。平台记录没有单独提供硬件型号，本地没有 NPU/CANN 编译器；下面的独立 runner 尚未实机验证：

~~~bash
cd operators/rotaryposemb
source /usr/local/Ascend/ascend-toolkit/set_env.sh
bash run.sh
cmake -S tools -B build-npu -DNPU_ARCH=dav-2201
cmake --build build-npu -j4
python3 tools/npu_validate.py --quick
python3 tools/npu_validate.py
python3 tools/package_submission.py
~~~

官方 run.sh 会重建 build 并运行公开 case 0。扩展工具提供 208 个本地生成用例（非隐藏测试集），可用 --generate-only 仅生成输入；runner 的 host_launch_batch_average_us 包含 host tiling、launch 和批次同步，不是纯设备时间。

打包产物在忽略的 dist/ 中，仅提交 kernel.asc。仓库仅纳入明确选取的验证/打包工具，不包含本地认证客户端、会话、账号文件或生成数据。
