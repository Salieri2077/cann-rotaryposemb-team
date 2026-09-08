#!/usr/bin/env python3
"""Recompute comparisons from saved online results; no platform requests."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo

DEFAULT_OPT = Path(__file__).resolve().parent / 'online'
KNOWN = {
    'baseline-a1': ('A1', 'baseline'), 'baseline-a2': ('A2', 'baseline'),
    'baseline-a3': ('A3', 'baseline'),
    'batch8guard4-g1': ('G1', 'batch8guard4'), 'batch8guard4-g2': ('G2', 'batch8guard4'),
    'batch8guard4multi-j1': ('J1', 'batch8guard4multi'),
    'pipeline-p1': ('P1', 'pipeline'), 'math-m1': ('M1', 'math'),
    'fixedwide-w1': ('W1', 'fixedwide'), 'theta1init-u1': ('U1', 'theta1init'),
}
EXPECTED_SHA = {
    'baseline': '1b772e01fa7c7e1c7e22ea4f79c4b052d553ffe1b5e3cc17f2d6e0c0a9e56bb8',
    'batch8guard4': '64ea1e92ea94220ea61a349df194864fc4948ad802e2b0b1eb73035a9c369085',
    'batch8guard4multi': 'e90f1f0279b41f429a7f687ed09fbfeffd7288bfd0412af2d431ae2af16cc625',
}

def geom(v):
    return math.exp(statistics.mean(math.log(x) for x in v))

def compare(candidate, reference, ids):
    ratios = {i: candidate[i] / reference[i] for i in ids}
    v = list(ratios.values())
    return dict(gmr=geom(v), change_percent=100 * (geom(v) - 1),
                median_point_ratio=statistics.median(v),
                min_point_change_percent=100 * (min(v) - 1),
                max_point_change_percent=100 * (max(v) - 1),
                faster_points=sum(x < 1 for x in v), slower_points=sum(x > 1 for x in v),
                raw_time_sum_ratio=sum(candidate.values()) / sum(reference.values()),
                point_ratios=ratios)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opt', type=Path, default=DEFAULT_OPT)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    sources, documents, values, labels = {}, {}, {}, {}
    paths = {p.stem.removeprefix('online-'): p for p in args.opt.glob('online-*.json')}
    for tag in sorted(set(paths) | set(KNOWN)):
        label, variant = KNOWN.get(tag, (tag, None))
        labels[tag] = label
        path = paths.get(tag, args.opt / f'online-{tag}.json')
        source = dict(label=label, path=str(path), variant=variant, status='Missing', comparable=False)
        sources[tag] = source
        if variant in EXPECTED_SHA:
            source['expected_kernel_sha256_from_submission_record'] = EXPECTED_SHA[variant]
        if variant:
            kernel = args.opt / variant / 'kernel.asc'
            if kernel.exists():
                source['current_kernel_artifact'] = str(kernel)
                source['current_kernel_sha256'] = hashlib.sha256(kernel.read_bytes()).hexdigest()
                if variant in EXPECTED_SHA:
                    source['current_kernel_matches_expected'] = source['current_kernel_sha256'] == EXPECTED_SHA[variant]
        if not path.exists():
            continue
        raw = path.read_bytes()
        source['sha256'] = hashlib.sha256(raw).hexdigest()
        try:
            doc = json.loads(raw)
            if not isinstance(doc, dict):
                raise ValueError('saved submission is not an object')
        except (ValueError, TypeError) as error:
            source.update(status='Unreadable', reason=str(error), raw_text=raw.decode(errors='replace'))
            continue
        documents[tag] = doc  # Preserve all returned rows, including failed/partial results.
        source.update(status=doc.get('status', 'Unknown'), submission_id=doc.get('_id'),
                      display_id=doc.get('ID'), created_at_utc=doc.get('create_time'))
        if doc.get('create_time'):
            try:
                source['created_at_china'] = datetime.fromisoformat(doc['create_time'].replace('Z', '+00:00')).astimezone(ZoneInfo('Asia/Shanghai')).isoformat()
            except (ValueError, TypeError):
                pass
        rows = doc.get('result')
        source['result_count'] = len(rows) if isinstance(rows, list) else None
        problems, point_values = [], {}
        if doc.get('status') != 'Pass':
            problems.append('submission is not Pass')
        if not isinstance(rows, list) or not rows:
            problems.append('no completed result rows')
        else:
            for row in rows:
                if not isinstance(row, dict):
                    problems.append('invalid row'); continue
                i = row.get('testcase_id')
                if not isinstance(i, str) or not i or i in point_values:
                    problems.append('missing/duplicate testcase_id'); continue
                try:
                    t = float(row['time'])
                except (KeyError, TypeError, ValueError):
                    problems.append(f'invalid time: {i}'); continue
                point_values[i] = t
                if not math.isfinite(t) or t <= 0:
                    problems.append(f'nonpositive/nonfinite time: {i}')
                if row.get('testcase_status') != 'Pass' or row.get('precision_ratio') != 1:
                    problems.append(f'nonpassing numerical result: {i}')
        source['exclusion_reasons'] = problems
        if not problems:
            values[tag] = point_values
    # IDs are joined as complete strings; A1 order is only a display convention.
    anchor_tag = next((t for t in ['baseline-a1', 'baseline-a2', 'baseline-a3'] if t in values and len(values[t]) == 15), None)
    ids = list(values[anchor_tag]) if anchor_tag else []
    for tag in list(values):
        if not ids or len(ids) != 15 or set(values[tag]) != set(ids):
            sources[tag]['exclusion_reasons'].append('testcase set differs from complete 15-point baseline')
            del values[tag]
        else:
            sources[tag]['comparable'] = True
    by_label = {labels[tag]: v for tag, v in values.items()}
    refs = {k: by_label[k] for k in ['A1', 'A2', 'A3'] if k in by_label}
    if 'A2' in refs and 'A3' in refs:
        refs['geometric_A2_A3_snapshot'] = {i: geom([refs['A2'][i], refs['A3'][i]]) for i in ids}
    if 'A1' in refs and 'A2' in refs:
        refs['geometric_A1_A2_snapshot_secondary'] = {i: geom([refs['A1'][i], refs['A2'][i]]) for i in ids}
    comparisons = {label: {r: compare(v, base, ids) for r, base in refs.items()}
                   for label, v in by_label.items() if label not in ['A1', 'A2', 'A3']}
    drift = {f'{new}_over_{old}': compare(by_label[new], by_label[old], ids)
             for old, new in [('A1', 'A2'), ('A2', 'A3'), ('A1', 'A3')]
             if old in by_label and new in by_label}
    required = ['G1', 'G2', 'A2', 'A3']
    repeated = dict(status='Waiting', missing_comparable=[k for k in required if k not in by_label],
                    candidate_rounds=['G1', 'G2'], reference_rounds=['A2', 'A3'],
                    excluded_from_candidate_average=['J1', 'P1', 'M1', 'W1', 'U1'],
                    expected_candidate_kernel_sha256=EXPECTED_SHA['batch8guard4'])
    if not repeated['missing_comparable']:
        candidate = {i: geom([by_label['G1'][i], by_label['G2'][i]]) for i in ids}
        reference = refs['geometric_A2_A3_snapshot']
        separated = [i for i in ids if max(by_label['G1'][i], by_label['G2'][i]) < min(by_label['A2'][i], by_label['A3'][i])]
        above = [i for i in ids if min(by_label['G1'][i], by_label['G2'][i]) > max(by_label['A2'][i], by_label['A3'][i])]
        repeated.update(status='Ready', geometric_candidate_times=candidate, geometric_reference_times=reference,
                        comparison=compare(candidate, reference, ids),
                        candidate_G2_over_G1=compare(by_label['G2'], by_label['G1'], ids),
                        both_candidate_runs_below_both_baselines=separated,
                        both_candidate_runs_above_both_baselines=above,
                        per_point_observed_ratio_range={i: [min(by_label[g][i] / by_label[a][i] for g in ['G1','G2'] for a in ['A2','A3']), max(by_label[g][i] / by_label[a][i] for g in ['G1','G2'] for a in ['A2','A3'])] for i in ids})
    rows = [dict(point_number_in_anchor_order=n+1, testcase_id=i,
                 times={label: v[i] for label, v in by_label.items()},
                 candidate_ratios={label: {r: c['point_ratios'][i] for r, c in cs.items()} for label, cs in comparisons.items()})
            for n, i in enumerate(ids)]
    report = dict(scope='Saved online NPU submissions; reads local files only',
                  generated_at_utc=datetime.now(ZoneInfo('UTC')).isoformat(),
                  metric='GMR=exp(mean(log(candidate_time/reference_time))) over 15 full matching testcase_id; <1 faster, not contest score',
                  caveats=['Two repeats are descriptive observations, not a confidence interval or significance test.',
                           'Geometric baseline snapshots are not noise correction or time interpolation.',
                           'API results do not contain kernel SHA: source association follows named submission records; local artifact SHA is reported separately.',
                           'No hidden shapes or official testcase_id mapping can be inferred from point numbers or timing.'],
                  sources=sources, raw_documents=documents, aligned_testcases=len(ids),
                  point_number_anchor=anchor_tag, baseline_drift=drift, candidate_comparisons=comparisons,
                  primary_guard4_repetition=repeated, points=rows)
    (args.out/'online_comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    lines = ['# 本轮线上结果独立复核', '',
             '按完整 testcase_id 对齐；点号只沿首个完整基线的返回顺序展示。全部原始结果（含失败、进行中及不可比较记录）保留在 JSON；仅完整 15/15 Pass 且 precision_ratio=1 的同一组点参与耗时比较。', '',
             'GMR 是等权耗时比几何平均，小于 1 表示更快，不是排行榜分数。主比较使用同源码 G1/G2 与 A2/A3；J1 独立，P1/M1/W1/U1 只作单次筛选。两轮观测不足以进行可靠显著性判断，基线几何快照不等于去噪或时间插值。', '',
             '| 提交 | 显示 ID | 状态 | 结果数 | 可比较 | 北京时间 |', '|---|---:|---|---:|---|---|']
    for tag, s in sources.items():
        lines.append(f"| {s['label']} | {s.get('display_id','—')} | {s['status']} | {s.get('result_count','—')} | {'是' if s['comparable'] else '否'} | {s.get('created_at_china','—')} |")
    lines += ['', '## guard4 两轮主比较', '']
    if repeated['status'] == 'Ready':
        c = repeated['comparison']
        pnums = lambda selected: ', '.join(str(ids.index(i)+1) for i in selected) or '无'
        lines += [f"G1/G2 逐点几何平均相对 A2/A3 逐点几何平均：GMR **{c['gmr']:.6f}**，耗时变化 **{c['change_percent']:+.3f}%**。这描述已有观测，不证明未来提交同样改善。", '',
                  f"两次 guard4 都低于两次基线的点：{pnums(repeated['both_candidate_runs_below_both_baselines'])}；两次都高于两次基线的点：{pnums(repeated['both_candidate_runs_above_both_baselines'])}。这里只比较四次观测范围，不称作统计显著。", '',
                  '| 点 / 完整 testcase_id | A2 | A3 | G1 | G2 | 两轮几何平均变化 | 四种实测比值范围 |', '|---|---:|---:|---:|---:|---:|---:|']
        for n, i in enumerate(ids):
            r = repeated['per_point_observed_ratio_range'][i]
            lines.append(f"| {n+1} / {i} | {by_label['A2'][i]:.2f} | {by_label['A3'][i]:.2f} | {by_label['G1'][i]:.2f} | {by_label['G2'][i]:.2f} | {(candidate[i]/reference[i]-1)*100:+.2f}% | {(r[0]-1)*100:+.2f}% ～ {(r[1]-1)*100:+.2f}% |")
    else:
        lines += [f"尚待完整可比较结果：{', '.join(repeated['missing_comparable'])}。不把 G1 单次观测写成两轮均值，也不把 J1 合入 guard4。"]
    lines += ['', '## 基线漂移', '', '| 基线比值 | GMR 耗时变化 | 逐点最小变化 | 逐点最大变化 |', '|---|---:|---:|---:|']
    for k, c in drift.items():
        lines.append(f"| {k} | {c['change_percent']:+.3f}% | {c['min_point_change_percent']:+.3f}% | {c['max_point_change_percent']:+.3f}% |")
    lines += ['', '基线漂移是同源码随提交时间变化的直接观测。不得用某次候选约百分之一的差异自动推断代码收益。总耗时和等权 GMR 分开保存；约毫秒级的大点不能用总和权重淹没其他点。', '',
              '## 各候选独立观测', '', '| 候选 | 对 A1 | 对 A2 | 对 A3 | 对 A2/A3 几何快照 |', '|---|---:|---:|---:|---:|']
    for label in sorted(comparisons):
        cs = comparisons[label]
        cell = lambda r: f"{cs[r]['change_percent']:+.3f}%" if r in cs else '待结果'
        lines.append('| '+label+' | '+' | '.join(cell(r) for r in ['A1','A2','A3','geometric_A2_A3_snapshot'])+' |')
    lines += ['', '上表是耗时变化，负数更快。J1 是不同分派条件，单独评价；P1/M1/W1/U1 没有相同候选重复，只作为筛选线索。完整逐点时间及对每个基线的比值保存在 JSON。', '',
              '## 证据边界', '',
              'guard4 源码预期 SHA-256 为 `'+EXPECTED_SHA['batch8guard4']+'`；G1/G2 的源码关联依本轮提交记录约定，平台结果本身不返回内核 SHA。JSON 另记当前本地源码哈希，避免把本地文件当作 API 提交内容证明。', '',
              '公开生成器只给出 H=1 的 case0；没有完整 testcase_id 映射或其他隐藏 shape，因此不能将 H5–8 的分派变化直接归因到某个线上点的具体形状。', '',
              '静态边界审查见 [guard4-review.md](guard4-review.md)。本脚本只重算保存的文件，不提交、不运行 NPU/CAModel。', '',
              f'复现：`python {Path(__file__).resolve()} --opt {args.opt} --out {args.out}`。新文件保存后重跑即可；没有完成结果的提交仅列状态。']
    (args.out/'online_comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(files_present=len(paths), comparable=len(values), statuses={s['label']:s['status'] for s in sources.values()},
                          primary_guard4_status=repeated['status'], missing=repeated['missing_comparable'],
                          primary_change_percent=repeated.get('comparison', {}).get('change_percent'),
                          outputs=[str(args.out/'online_comparison.json'),str(args.out/'online_comparison.md')]), ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
