"""Recompute comparisons from the recorded CANNJudge times; no network access."""
import json
import math
from pathlib import Path


def geometric_latency_reduction(baseline, candidate):
    ratio = math.exp(sum(math.log(y / x) for x, y in zip(baseline, candidate)) / len(baseline))
    return 100 * (1 - ratio)


def main():
    data = json.loads(Path(__file__).with_name('results.json').read_text())
    runs = {run['tag']: run for run in data['runs']}
    tags = ('baseline_a', 'baseline_b', 'position', 'position_b')
    ids = [item['testcase_id'] for item in runs['baseline_a']['result']]
    for tag in tags:
        assert runs[tag]['status'] == 'Pass'
        assert [item['testcase_id'] for item in runs[tag]['result']] == ids
        assert all(item['testcase_status'] == 'Pass' and item['precision_ratio'] == 1
                   for item in runs[tag]['result'])
    times = {tag: [item['time'] for item in runs[tag]['result']] for tag in tags}
    baseline = [(x + y) / 2 for x, y in zip(times['baseline_a'], times['baseline_b'])]
    candidate = [(x + y) / 2 for x, y in zip(times['position'], times['position_b'])]
    print(json.dumps({
        'metric': 'percent latency reduction; positive means faster',
        'time_unit': data['time_unit'],
        'repeats_per_source': 2,
        'geometric_mean_ratio_reduction': geometric_latency_reduction(baseline, candidate),
        'sum_of_case_times_reduction': 100 * (1 - sum(candidate) / sum(baseline)),
        'paired_run_reductions': [
            geometric_latency_reduction(times['baseline_a'], times['position']),
            geometric_latency_reduction(times['baseline_b'], times['position_b'])],
        'per_case': [dict(case=i, baseline_mean=x, candidate_mean=y, reduction=100 * (1 - y / x))
                     for i, (x, y) in enumerate(zip(baseline, candidate), 1)],
    }, indent=2))


if __name__ == '__main__':
    main()
