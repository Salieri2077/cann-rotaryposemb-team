#!/usr/bin/env python3
"""Compare a runner output against the stored references; does not execute a kernel."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('case_dir',type=Path)
parser.add_argument('--output',type=Path,help='Default: CASE_DIR/y.bin')
args=parser.parse_args()
meta=json.loads((args.case_dir/'case.json').read_text())
dtype=np.dtype(meta['dtype']);shape=tuple(meta['shape'])
output=args.output or args.case_dir/'y.bin'
if not output.is_file():
 parser.error(f'No runner output exists: {output}; no simulation result can be checked yet')
actual=np.fromfile(output,dtype=dtype)
expected_size=int(np.prod(shape))
if actual.size!=expected_size:
 parser.error(f'Output has {actual.size} elements; expected {expected_size}')
atol=rtol=1e-4 if dtype==np.float32 else 1e-3
checks={}
for name,file in (('same_powf','golden_powf.bin'),('official_numpy','golden_numpy.bin')):
 expected=np.fromfile(args.case_dir/file,dtype=dtype)
 close=np.isclose(actual.astype(np.float32),expected.astype(np.float32),rtol=rtol,atol=atol,equal_nan=True)
 finite=np.isfinite(actual)&np.isfinite(expected)
 mismatch=float(1-close.mean())
 error=float(np.abs(actual.astype(np.float64)-expected.astype(np.float64))[finite].max(initial=0))
 checks[name]={'pass':mismatch<=1e-4,'mismatch_fraction':mismatch,'max_abs_error':error}
report={'kind':'output_comparison_only','output':str(output.resolve()),'kernel_sha256':meta['kernel_sha256'],
        'shape':shape,'dtype':meta['dtype'],'local_rtol':rtol,'local_atol':atol,
        'max_mismatch_fraction':1e-4,'references':checks}
with (args.case_dir/'comparison.json').open('x') as report_file:
    report_file.write(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(0 if all(item['pass'] for item in checks.values()) else 1)
