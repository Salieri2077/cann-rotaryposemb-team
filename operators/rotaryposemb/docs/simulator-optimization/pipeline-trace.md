# Low-H pipeline trace comparison

Only existing official CAModel traces were read. No simulator, build or submission was run. Input [1,257,3,32] FP32, theta=10000, seed=2026090804, requested cores=1. Input hashes match exactly. Kernel SHA: baseline `1b772e01fa7c7e1c7e22ea4f79c4b052d553ffe1b5e3cc17f2d6e0c0a9e56bb8`, candidate `be5191da6ea7eea871486f641d4a8d3efb74a49246f61a99d70e0082d41c4d71`.

| Measured interval (us) | Baseline | Candidate |
|---|---:|---:|
| Instruction window, excluding initial CACHEMISS | 25.908001 | 21.914001 |
| Batch-loop MTE2→Scalar flag7 waits, union | 4.356757 | 0.003784 |
| Explicit Position MTE2→Scalar flag0 waits, union | 0.830270 | 0.830811 |
| Vector ∩ MTE2 non-sync in-flight intervals | 2.232998 | 4.470998 |
| X DMA ∩ FinishTrig Vector intervals | 0.000000 | 3.991996 |
| Vector ∩ MTE3 non-sync in-flight intervals | 2.583001 | 3.525997 |
| MTE2 ∩ MTE3 non-sync in-flight intervals | 2.205001 | 0.652999 |

Instruction window falls by 3.994000 us (15.42%). Each trace still has **264 flag7 MTE2→Scalar WAIT instructions**, including 257 zero-duration Position/GetValue waits and 7 batch-loop waits. The optimization shortens those batch waits; it does not remove seven synchronization instructions. Loop nearest-source mapping moves from baseline line 1034 to candidate line 1033. Actual Position wait remains line 528.

Scalar non-sync instruction instances increase from 17473 to 19413 (+1940); their in-flight union rises from 15.896651 to 16.511696 us. Thus the gain is not a reduction in total instruction work. The compiler-generated Scalar cost needs separate investigation if other shapes regress. MTE2/MTE3 overlap also decreases, so not every pair of pipelines overlaps more.

The instruction timing is consistent with removing the current X transfer from the dependency chain before Scalar position reads and increasing X/trig overlap. It does not establish an exclusive causal decomposition: other instructions can execute during waits, and different overlap intervals are not additive. Do not equate the wait decrease with a separately recoverable speedup.

Vector non-sync opcode counts equal: **True**. DMA non-sync opcode counts equal: **True**. Each trace is independently cross-checked against its official instruction CSV by opcode/PC/pipe instance count. The full JSON records file hashes, source-derived function bounds, pipeline unions, DMA subsets and every batch flag7 wait interval/PC.

These are simulator in-flight intervals, not PMU utilization, exclusive service cycles, physical NPU timings or hidden judge cases. This comparison alone says nothing about the wide-angle paired case or other shapes. Reproduce with `python /tmp/rope-opt-pipeline/trace_comparison.py`.
