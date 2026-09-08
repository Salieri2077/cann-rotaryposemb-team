# RotaryPosEmb 团队算子

当前内核采用经过 CANN 仿真与线上测试的中等 head 批处理优化：在容量和核数条件满足时，将 H=5–8 输入交给现有批处理路径。最终提交 **243107**，同一源码两轮均 **15/15 Pass**；第 6 点两轮约缩短 **26%**，15 点等权耗时比几何平均约下降 **1.91%**。完整复测、全部候选和测量边界见[本轮报告](docs/simulator-optimization/README.md)。源码 SHA `64ea1e92ea94220ea61a349df194864fc4948ad802e2b0b1eb73035a9c369085`。

## 实现

小张量专用路径：FP32、D16、H1且token数不超过可用核心数时，每核处理完整token；仅传36B配置，使用416B临时存储及显式DMA事件，省去通用队列。其他输入继续使用通用实现。第一个测试点由此前最好版本的3.42降至2.99，约下降12.6%。[专项设计与验证](docs/sprint65/one_token_design.md)。

- 保留官方 FP16/FP32 输入、前后半维旋转、FP32 中间计算与 run_kernel 签名。
- positions 采用 256B 单缓存，以 MTE2_S 与 S_MTE2 直接同步搬运和标量访问，去除多余的向量队列依赖。
- 跨 token 批量计算联合 Sin/Cos。H≤4 保持原策略；H=5–8 在 token 数和缓冲容量满足时合批，其余输入使用共享系数、整行向量计算和双缓冲。
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

本轮通过实际源码 CPU 的 230 个数值用例、47 个批处理定向逐位对照、96 个 UB/边界用例、1,812,272 种实际 host 配置、11 个入口 stub 语法检查及 11,160 组基础回归。另有真实 CANN 编译、官方 CAModel 1/32 核运行及线上评测；各自范围见[验证记录](docs/simulator-optimization/validation.json)。CPU 模型不模拟异步设备性能。

本机NumPy2.4.4 SIMD power与host powf舍入不同，230例中107例超过本地严格阈值，该诊断独立保留；同powf独立参考通过。最终平台正确性以15点正式结果为依据。

## NPU与打包

目标为 CANN 9.0 / dav-2201，平台未独立报告具体硬件型号。本地已安装官方 CANN 9.0.0 编译器并运行 CAModel，没有实体 NPU。无卡复现见 [CAModel 工具](tools/camodel/README.md)；以下命令用于具备真实 NPU 的环境。

```sh
source /usr/local/Ascend/ascend-toolkit/set_env.sh
bash run.sh
cmake -S tools -B build-npu -DNPU_ARCH=dav-2201
cmake --build build-npu -j4
python3 tools/npu_validate.py --quick
```

官方run.sh运行公开case0；扩展runner可生成208个本地用例，其host_launch_batch_average_us含主机分块、启动及同步，不代表纯设备时间。打包产物位于忽略的dist目录，只提交kernel.asc。

仓库仅包含选取的算子与验证工具；历史基线与实验回退结果见[RESULTS](RESULTS.md)。
