#!/usr/bin/env python3
"""Execute the actual kernel body with a synchronous, bounds-checking CPU API model.

This checks indexing/tiling/arithmetic/queue ownership. It does NOT validate CANN
compilation, device asynchronous hazards, NPU Sin/Cos precision, or performance.
A separate diagnostic measures NumPy vs host-libm inverse-frequency differences.
"""
import argparse
import ctypes
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "tests" / "cpu_sim"

def build():
    directory = Path(tempfile.mkdtemp(prefix="rope_cpu_sim_"))
    source = (ROOT / "kernel.asc").read_text()
    for dtype in ("float", "half"):
        old = (f"rotary_pos_emb_draft<{dtype}><<<cfg.blockCount, nullptr, stream>>>"
               "(x, positions, y, cfg);")
        new = ("{ ++sim::launches; for (sim::block=0; sim::block<cfg.blockCount; ++sim::block) "
               f"rotary_pos_emb_draft<{dtype}>(x, positions, y, cfg); }}")
        if source.count(old) != 1:
            raise RuntimeError("Kernel launch changed; update this transparent CPU adapter")
        source = source.replace(old, new)
    (directory / "kernel_cpu.inc").write_text(source)
    lib = directory / "kernel_sim.so"
    subprocess.run([
        "g++", "-std=c++17", "-O2", "-shared", "-fPIC",
        "-fno-fast-math", "-ffp-contract=off",
        "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        "-I", str(SIM), "-I", str(directory),
        str(SIM / "driver.cpp"), "-o", str(lib),
    ], check=True)
    dll = ctypes.CDLL(str(lib))
    fn = dll.sim_run
    fn.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_int64] * 4 + [
        ctypes.c_int32, ctypes.c_int64, ctypes.c_float]
    fn.restype = ctypes.c_int
    reduce = dll.sim_reduce
    reduce.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    reduce.restype = None
    return fn, reduce

spec = importlib.util.spec_from_file_location("official_rope", ROOT / "scripts" / "RotaryPosEmb.py")
golden_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(golden_module)

libm = ctypes.CDLL("libm.so.6")
libm.powf.argtypes = [ctypes.c_float, ctypes.c_float]
libm.powf.restype = ctypes.c_float

def powf_reference(x, positions, theta):
    """Independent array reference using host powf to isolate kernel arithmetic."""
    d = x.shape[-1]
    exponent = np.arange(0, d, 2, dtype=np.float32) / d
    power = np.array([libm.powf(float(theta), float(e)) for e in exponent], dtype=np.float32)
    inv = np.float32(1) / power
    phase = positions.astype(np.float32)[..., None] * inv
    cosine, sine = np.cos(phase)[..., None, :], np.sin(phase)[..., None, :]
    a, b = np.split(x.astype(np.float32), 2, axis=-1)
    return np.concatenate([a * cosine - b * sine, b * cosine + a * sine], axis=-1).astype(x.dtype)

def comparison(actual, expected, dtype):
    atol = rtol = 1e-4 if dtype == np.float32 else 1e-3
    close = np.isclose(actual.astype(np.float32), expected.astype(np.float32),
                       rtol=rtol, atol=atol, equal_nan=True)
    finite = np.isfinite(actual) & np.isfinite(expected)
    error = np.abs(actual.astype(np.float64) - expected.astype(np.float64))
    return float(1 - close.mean()), float(error[finite].max(initial=0))

def check_wide_reduction(reduce):
    rng = np.random.default_rng(314159)
    bits = rng.integers(0, 2**32, 250000, dtype=np.uint32)
    angles = bits.view(np.float32)
    angles = angles[np.isfinite(angles)]
    edges = np.array([0., -0., np.pi, -np.pi, np.finfo(np.float32).max,
                      -np.finfo(np.float32).max], dtype=np.float32)
    angles = np.concatenate([angles, edges])
    output = np.empty_like(angles)
    reduce(angles.ctypes.data, output.ctypes.data, angles.size)
    sin_error = float(np.max(np.abs(np.sin(angles.astype(np.float64)) -
                                   np.sin(output.astype(np.float64)))))
    cos_error = float(np.max(np.abs(np.cos(angles.astype(np.float64)) -
                                   np.cos(output.astype(np.float64)))))
    assert np.all(np.isfinite(output))
    assert np.max(np.abs(output)) <= np.float32(np.pi)
    assert max(sin_error, cos_error) < 4e-7, (sin_error, cos_error)
    assert not np.signbit(output[-6]) and np.signbit(output[-5])
    exceptional = np.array([np.inf, -np.inf, np.nan], dtype=np.float32)
    reduced_exceptional = np.empty_like(exceptional)
    reduce(exceptional.ctypes.data, reduced_exceptional.ctypes.data, 3)
    assert np.all(np.isnan(reduced_exceptional))
    return dict(cases=int(angles.size), sin_max_error=sin_error,
                cos_max_error=cos_error, signed_zero_and_nonfinite="passed")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "cpu_sim_report.json")
    args = parser.parse_args()
    run, reduce = build()
    scalar_report = check_wide_reduction(reduce)
    rng = np.random.default_rng(271828)
    shapes = [
        (1, 7, 1, 16), (2, 16, 3, 24), (1, 1, 256, 64),
        (2, 17, 128, 64), (1, 65, 1, 16), (1, 129, 4, 32),
        (1, 17, 5, 18), (1, 9, 9, 30), (1, 3, 127, 66),
        (1, 2, 3, 1024), (1, 5, 5, 1022), (2, 3, 8, 510),
        (1, 97, 1, 24), (1, 37, 3, 20), (1, 5, 256, 32),
        (1, 7, 1, 512), (1, 9, 3, 514), (1, 5, 5, 530),
        (1, 3, 17, 768), (1, 2, 256, 1024),
        (1, 7, 1, 686), (1, 9, 3, 688), (1, 5, 5, 690),
    ]
    records = []
    max_kernel_error = 0.0
    failures = []
    for dtype in (np.float32, np.float16):
        for j, shape in enumerate(shapes):
            for pmax, theta in ((50, 10000.0), (131073, 10000.0), (131073, 1.0),
                                (131073, 0.5), (131073, 1e-6)):
                x = rng.uniform(-10, 10, shape).astype(dtype)
                p = rng.integers(0, pmax, shape[:2], dtype=np.int32)
                p.flat[0] = 0
                if p.size > 1:
                    p.flat[-1] = pmax - 1
                y = np.full(shape, np.nan, dtype=dtype)
                cores = (1, 8, 32)[j % 3]
                status = run(x.ctypes.data, p.ctypes.data, y.ctypes.data,
                             *shape, 0 if dtype == np.float32 else 1, cores, theta)
                if status != 0:
                    raise AssertionError(f"CPU model execution failed: {shape}, {dtype}")
                isolated = powf_reference(x, p, theta)
                mismatch, error = comparison(y, isolated, dtype)
                max_kernel_error = max(max_kernel_error, error)
                if mismatch > 1e-4:
                    failures.append((shape, str(dtype), pmax, theta, mismatch, error))
                official = golden_module.impl(x, p, theta)
                official_mismatch, official_error = comparison(y, official, dtype)
                records.append(dict(shape=shape, dtype=np.dtype(dtype).name,
                    cores=cores, max_position=int(p.max()), theta=theta,
                    isolated_kernel_mismatch=mismatch, isolated_max_error=error,
                    numpy_golden_mismatch=official_mismatch,
                    numpy_golden_max_error=official_error))
    report = dict(
        model="synchronous CPU execution of kernel.asc; not CANN/NPU validation",
        numpy_version=np.__version__, cases=len(records),
        scalar_reduction=scalar_report,
        isolated_failures=failures, isolated_max_abs_error=max_kernel_error,
        numpy_diagnostic_failed_cases=sum(r["numpy_golden_mismatch"] > 1e-4 for r in records),
        cases_detail=records)
    report_path = args.report
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"CPU kernel model: {len(records)-len(failures)}/{len(records)} "
          "passed against independent same-powf reference.")
    print(f"NumPy golden diagnostic: {report['numpy_diagnostic_failed_cases']} "
          "cases exceeded local strict tolerance; inspect power rounding before NPU validation.")
    print(f"Scalar reduction: {scalar_report}")
    print(f"Report: {report_path}")
    if failures:
        raise AssertionError(f"Actual kernel arithmetic/indexing failures: {failures[:8]}")

if __name__ == "__main__":
    main()
