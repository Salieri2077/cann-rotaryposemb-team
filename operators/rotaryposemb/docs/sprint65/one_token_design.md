# 小张量单token入口

最终源码对应提交230746，SHA-256 `3616b92cf7c5ed62916ebbd0432756192816b5081d20af72bbcf5e4c1bbc2c26`，平台15/15 Pass，核查时第5名、10.41分。源文件为算子目录的kernel.asc。

仅FP32、D=16、H=1且B*S不超过可用核心数及65535时使用专用入口。每个核心按blockIdx处理一个完整token，启动后立即返回；其他输入保留已通过的通用实现。分派仅依赖公开shape/dtype/core数，无固定输入、答案或跨调用缓存。

配置包含wideAngles和每次调用重新生成的8个原始FP32频率，共36B；加3个64位地址，源级参数为60B，实际尾部对齐由ABI决定。频率仍为1/powf(theta,2*i/16)，FinishTrig与通用版本相同，保留任意合法theta的大角度处理。旋转采用四个独立Mul、一个屏障及Sub/Add，保留分离舍入。

一个TBuf<VECIN>占416B：输入64B、输出64B、带padding的位置32B、频率32B、七个三角临时区224B。所有区域32B对齐且不重叠。每核心实际读取64B输入和4B位置，输出64B；不分配或操作TQue。

显式事件保护全部依赖：MTE2_S保护位置标量读取，S_V保护频率向量读取，MTE2_V在旋转首次读取输入前等待，V_MTE3保护输出DMA，MTE3_S在返回前等待搬运完成。大角度路径保留V_S/S_V，事件均从FetchEventID取得并成对使用。

官方依据：[DataCopyPad支持GM与VECIN双向搬运](https://www.hiascend.com/document/detail/zh/canncommercial/850/API/ascendcopapi/atlasascendc_api_07_0265.html)，[事件同步](https://www.hiascend.com/document/detail/en/canncommercial/850/API/ascendcopapi/atlasascendc_api_07_0270.html)。

验证包括998个通用实际kernel用例，以及1191个专项配置（621次命中新入口、570次通用入口）。专项覆盖核心数阈值两侧、B>1展平、相邻未选中shape/dtype、位置0及边界、最小FP32正数至1e38的theta，严格同powf参考通过，与此前最好版本逐位相同；DMA次数、字节数、TBuf/TQue次数及事件数量均有断言。测试默认无需本地基线文件；--baseline可额外对给定源码做逐位比较。

所有11个入口变体通过Clang的C++14语法检查；只对CPU stub移除inline变量，生产代码除启动语法适配外原样。CPU不模拟设备异步流水，最终编译和正确性已有平台15点验证。单次性能测量仍可能包含噪声。
