# RotaryPosEmb 团队算子

当前内核对应提交 **230746**，平台 **15/15 Pass**，本轮基准分数 **10.41**。[正式评测](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e99f2bf41025d6015c51c)；[本轮逐项实验](docs/sprint65/README.md)。此前 56.97 分采用另一组 best_time，不能直接与本轮分数比较。2026-09-07本次核查第5名，已达到前6目标；排名会随其他提交变化。

## 实现

小张量专用路径：FP32、D16、H1且token数不超过可用核心数时，每核处理完整token；仅传36B配置，使用416B临时存储及显式DMA事件，省去通用队列。其他输入继续使用通用实现。第一个测试点由此前最好版本的3.42降至2.99，约下降12.6%。[专项设计与验证](docs/sprint65/one_token_design.md)。

- 保留官方 FP16/FP32 输入、前后半维旋转、FP32 中间计算与 run_kernel 签名。
- 跨 token 批量计算联合 Sin/Cos，低 head 广播系数；共享 head 使用整行向量计算和双缓冲。
- D16/32/64/128 使用 136/168/232/360B 参数，其他维度保持不超过 1472B；每次调用恰好一次核函数启动。
- 前两段范围约简用精确乘积 Axpy；大角度仍走整数 Payne–Hanek，保持原精度阈值。
- 对齐行使用连续 DMA，低 head 的 D128 及满足行数约束的 D16 FP32 合并搬运；其余保留带填充布局。
- 按完整32B边界分配跨核输出、64位GM地址；4K I/O tile的角度上限1536，最大UB分配192800B。
- 频率由每次调用的 theta 重新生成，宽维度采用无损位型残差编码，正常数乘法采用精确整数快速路径。

分派只使用公开 shape、dtype、theta 和对齐条件。7个官方只读文件逐字节一致；golden与精度阈值未改动。

## 验证

在本目录执行（Python需要NumPy，实际内核模型还需要g++）：

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/test_host_tiling.py
python3 tests/run_cpu_kernel.py
python3 tests/check_contiguous.py
python3 tests/check_lowh.py
python3 tests/check_midh.py
python3 tests/check_window.py
python3 tests/check_ub_capacity.py
python3 tests/check_joint_sincos.py
python3 tests/check_one_token.py
python3 tests/check_cpp14.py
python3 tools/check_template.py
python3 tools/package_submission.py
```

实际 kernel 主体经透明启动语法适配后运行CPU模型，共998个数值/布局用例，另1191个专项用例检查小张量分派、精度、DMA范围和事件数量；host分块覆盖1,812,272种配置，包含跨核32B对齐、范围覆盖和UB预算。全部11个设备入口变体通过C++14语法检查。标量约简249,042样本、联合三角函数17,000,008点扫描通过。模型检查地址、队列容量及每次一次launch，不模拟设备异步流水或性能。

本机NumPy2.4.4 SIMD power与host powf舍入不同，230例中107例超过本地严格阈值，该诊断独立保留；同powf独立参考通过。最终平台正确性以15点正式结果为依据。

## NPU与打包

目标为CANN9.0 / dav-2201，平台未独立报告具体硬件型号。本地没有CANN编译器或NPU；独立runner尚未实机验证。

```sh
source /usr/local/Ascend/ascend-toolkit/set_env.sh
bash run.sh
cmake -S tools -B build-npu -DNPU_ARCH=dav-2201
cmake --build build-npu -j4
python3 tools/npu_validate.py --quick
```

官方run.sh运行公开case0；扩展runner可生成208个本地用例，其host_launch_batch_average_us含主机分块、启动及同步，不代表纯设备时间。打包产物位于忽略的dist目录，只提交kernel.asc。

仓库仅包含选取的算子与验证工具；历史基线与实验回退结果见[RESULTS](RESULTS.md)。
