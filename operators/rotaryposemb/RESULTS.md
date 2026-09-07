# Current implementation — submission 230746

**15/15 Pass, 10.4053 points** on the captured reference; verified rank5 on2026-09-07. [Submission](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9e99f2bf41025d6015c51c).

Reference times changed during this sprint. The previous 229648 score of 56.97 uses a different reference and is retained in [earlier experiments](docs/optimization/README.md). [Current experiment history](docs/sprint65/README.md) records improvements and regressions without changing the golden or tolerances.

| Case | time | best_time | Status |
| --- | ---: | ---: | --- |
| 1 | 2.99 | 1.18 | Pass |
| 2 | 5.52 | 0.57 | Pass |
| 3 | 8.43 | 0.58 | Pass |
| 4 | 17.04 | 0.59 | Pass |
| 5 | 19.31 | 0.58 | Pass |
| 6 | 31.08 | 0.57 | Pass |
| 7 | 28.75 | 0.59 | Pass |
| 8 | 15.86 | 0.61 | Pass |
| 9 | 45.46 | 0.57 | Pass |
| 10 | 6499.94 | 0.57 | Pass |
| 11 | 45.51 | 0.6 | Pass |
| 12 | 57.99 | 0.59 | Pass |
| 13 | 349.69 | 0.56 | Pass |
| 14 | 869.44 | 0.55 | Pass |
| 15 | 289.44 | 0.56 | Pass |

API time values are preserved without asserting units. CANN9.0 / dav-2201; exact hardware model not independently reported. No local NPU. CPU checks include 998 actual-kernel configurations and 1,812,272 host tiling configurations; numerical-model limitations are documented in the README.

# Previous platform baseline — submission 224901

- Submitter: swlaird
- Submitted: 2026-09-06 18:31:44 UTC (2026-09-07 02:31:44 Asia/Shanghai)
- Status: **Pass, 15/15**, all precision_ratio values are 1
- Recorded leaderboard score: **43.58**
- CANN: 9.0; target architecture: dav-2201; exact judge hardware model not independently reported
- Source SHA-256: ef06d7759dfddd0f5e2d281d5497acb900591d36086de4e59e13e80a71417194
- [Submission](https://cannjudge.cn/public/op_challenge_jingdong_prelim/rotaryposemb/submission/6a9db190bf41025d60db0a29)

Times below preserve the API values; no independent assertion about their units.

| Case | Status | precision_ratio | time | best_time |
| --- | --- | --- | --- | --- |
| 1 | Pass | 1 | 4.69 | 2.01 |
| 2 | Pass | 1 | 6.12 | 3.99 |
| 3 | Pass | 1 | 15.68 | 5.99 |
| 4 | Pass | 1 | 20.68 | 10.93 |
| 5 | Pass | 1 | 25.12 | 13.24 |
| 6 | Pass | 1 | 46.28 | 13.5 |
| 7 | Pass | 1 | 36.99 | 18.9 |
| 8 | Pass | 1 | 26.6 | 12.21 |
| 9 | Pass | 1 | 58.37 | 36.18 |
| 10 | Pass | 1 | 8495.74 | 6422.19 |
| 11 | Pass | 1 | 81.57 | 40.76 |
| 12 | Pass | 1 | 166.54 | 72.34 |
| 13 | Pass | 1 | 364.74 | 330.1 |
| 14 | Pass | 1 | 1054.86 | 852.24 |
| 15 | Pass | 1 | 452.71 | 293.71 |

CPU checks: 230/230 against an independent same-powf reference; 1,812,272 host tiling configurations; 249,042 scalar reduction samples. Each modeled call checks exactly one kernel launch. This does not substitute for NPU testing. The independent NPU runner has not been compiled or run locally.

## Previous team baseline

The following historical record is preserved for comparison; its kernel remains in Git history.

### Platform Evaluation

Date: 2026-09-06
Submission: `6a9d8568bf41025d60d073e9`
Overall status: `Pass`

The `time` column below preserves the API values without independently
asserting their units. The existing client labels them as milliseconds.

| Case | Status | precision_ratio | time |
| --- | --- | --- | --- |
| 1 | Pass | 1 | 3.98 |
| 2 | Pass | 1 | 6.06 |
| 3 | Pass | 1 | 25.7 |
| 4 | Pass | 1 | 43.59 |
| 5 | Pass | 1 | 92.48 |
| 6 | Pass | 1 | 115.89 |
| 7 | Pass | 1 | 162.26 |
| 8 | Pass | 1 | 102.74 |
| 9 | Pass | 1 | 298.4 |
| 10 | Pass | 1 | 44418.38 |
| 11 | Pass | 1 | 429.14 |
| 12 | Pass | 1 | 753.99 |
| 13 | Pass | 1 | 535.06 |
| 14 | Pass | 1 | 2498.18 |
| 15 | Pass | 1 | 1195.38 |

CPU regression: 11160 numerical combinations passed. Maximum trig absolute
error in the CPU model: `2.384185791015625e-7`; maximum FP32 rotation absolute
error: `4.76837158203125e-7`. These CPU numbers are not NPU error measurements.
