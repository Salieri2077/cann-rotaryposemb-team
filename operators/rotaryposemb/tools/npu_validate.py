#!/usr/bin/env python3
"""Generate stress inputs and run the independent NPU executable against official NumPy golden.

These are additional local cases, not the hidden judge suite. --generate-only
performs no NPU test. Timing includes host tiling/launch and batch synchronization.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("official_rope", ROOT / "scripts/RotaryPosEmb.py")
golden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(golden)

SHAPES = [(1, 7, 1, 16), (1, 37, 3, 20), (2, 17, 1, 24), (1, 9, 9, 30),
          (1, 1, 256, 64), (1, 65, 4, 32), (2, 17, 128, 64),
          (1, 5, 5, 1022), (1, 2, 3, 1024), (1, 97, 1, 18),
          (1, 7, 1, 512), (1, 9, 3, 514), (1, 5, 5, 530)]

def compare(actual, expected, dtype):
    if actual.shape != expected.shape:
        return {"pass": False, "reason": "output element count differs from golden"}
    # Published dtype tolerances, with the public case's mismatch-fraction rule.
    # Hidden per-case settings are not exposed by the downloaded template.
    atol = rtol = 1e-4 if dtype == np.float32 else 1e-3
    close = np.isclose(actual.astype(np.float32), expected.astype(np.float32),
                       rtol=rtol, atol=atol, equal_nan=True)
    finite = np.isfinite(actual) & np.isfinite(expected)
    with np.errstate(invalid="ignore"):
        absolute = np.abs(actual.astype(np.float64) - expected.astype(np.float64))
    max_error = float(absolute[finite].max(initial=0))
    mismatch_fraction = float(1 - close.mean())
    return {"pass": mismatch_fraction <= 1e-4,
            "mismatch_fraction": mismatch_fraction, "max_finite_absolute_error": max_error,
            "local_rtol": rtol, "local_atol": atol, "local_max_mismatch_fraction": 1e-4}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, default=ROOT / "build-npu/rope_npu_runner")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build-npu/cases")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--quick", action="store_true", help="Only the public shape and small positions")
    args = parser.parse_args()
    if args.iterations < 1 or args.device < 0:
        parser.error("iterations must be positive and device nonnegative")
    if not args.generate_only and not args.runner.is_file():
        parser.error("NPU runner missing: build tools/CMakeLists.txt first, or use --generate-only")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(271828)
    records = []
    shapes = SHAPES[:1] if args.quick else SHAPES
    limits = (50,) if args.quick else (50, 131073)
    types = (np.float32,) if args.quick else (np.float32, np.float16)
    for dtype in types:
        for shape in shapes:
            for limit in limits:
                for theta in ((10000.0,) if args.quick else (10000.0, 1.0, 0.5, 1e-6)):
                    name = f"case_{len(records):03d}"
                    directory = args.output_dir / name
                    directory.mkdir(parents=True, exist_ok=True)
                    x = rng.uniform(-10, 10, shape).astype(dtype)
                    p = rng.integers(0, limit, shape[:2], dtype=np.int32)
                    p.flat[0] = 0
                    if p.size > 1:
                        p.flat[-1] = limit - 1
                    expected = golden.impl(x, p, theta)
                    x.tofile(directory / "x.bin")
                    p.tofile(directory / "positions.bin")
                    expected.tofile(directory / "golden_y.bin")
                    record = {"name": name, "shape": shape, "dtype": np.dtype(dtype).name,
                              "theta": theta, "max_position": int(p.max()),
                              "npu_executed": False}
                    (directory / "case.json").write_text(json.dumps(record, indent=2) + "\n")
                    if not args.generate_only:
                        command = [str(args.runner.resolve()), str(directory.resolve()),
                                   *map(str, shape), np.dtype(dtype).name, str(theta),
                                   str(args.iterations), str(args.device)]
                        try:
                            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
                            record.update(npu_executed=True, returncode=result.returncode,
                                          runner_stdout=result.stdout.strip(), runner_stderr=result.stderr.strip())
                            if result.returncode != 0:
                                record.update({"pass": False, "reason": "runner failed"})
                            else:
                                actual = np.fromfile(directory / "y.bin", dtype=dtype)
                                record.update(compare(actual, expected.reshape(-1), dtype))
                        except (subprocess.TimeoutExpired, OSError) as error:
                            record.update({"pass": False, "reason": str(error)})
                    records.append(record)
                    if not args.generate_only:
                        print(name, "PASS" if record.get("pass") else "FAIL", flush=True)
    summary = {"kind": "generated_only" if args.generate_only else "npu_execution",
               "hidden_judge_cases": False, "cases": records}
    report = args.output_dir / "validation.json"
    report.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"{len(records)} cases; report: {report}")
    if args.generate_only:
        print("Input generation only: no NPU execution, precision validation, or timing was performed.")
    return 0 if args.generate_only or all(r.get("pass", False) for r in records) else 1

if __name__ == "__main__":
    raise SystemExit(main())
