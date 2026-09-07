# Platform Evaluation

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
