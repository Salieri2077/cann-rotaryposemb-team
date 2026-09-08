#!/usr/bin/env python3
"""Stage, build, and profile synthetic RotaryPosEmb cases with CANN CAModel.

Staging generates data/references only. Build/run require an installed CANN
environment. No installation, download, hardware execution, or judge submission.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
COMPONENTS = ("CMakeLists.txt", "sim_runner.asc", "check_output.py", "run_profiles.py")
CASE_FILES = ("case.json", "x.bin", "positions.bin", "golden_powf.bin", "golden_numpy.bin")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def manifest_files(root):
    paths = [root / "kernel.asc", *(root / name for name in COMPONENTS)]
    paths += sorted((root / "data").rglob("*.bin"))
    paths += sorted((root / "data").rglob("*.json"))
    return {str(path.relative_to(root)): sha(path) for path in paths}


def verify(root):
    manifest = json.loads((root / "manifest.json").read_text())
    for relative, expected in manifest["files_sha256"].items():
        if sha(root / relative) != expected:
            raise ValueError(f"Staged file changed: {relative}; use a new work directory")
    return manifest


def stage(args):
    import numpy as np
    kernel = args.kernel.resolve(strict=True)
    operator = args.operator_root.resolve(strict=True)
    references = [operator / "tests/run_cpu_kernel.py", operator / "scripts/RotaryPosEmb.py"]
    for path in (*references, *(HERE / name for name in COMPONENTS)):
        if not path.is_file():
            raise ValueError(f"Missing source component: {path}")
    cases = json.loads(args.cases.read_text()) if args.cases else [{
        "name": args.name, "shape": args.shape, "dtype": args.dtype,
        "theta": args.theta, "seed": args.seed, "max_position": args.max_position}]
    if not isinstance(cases, list) or not cases:
        raise ValueError("--cases must contain a nonempty JSON list")
    names = set()
    for case in cases:
        case.setdefault("dtype", "float32")
        case.setdefault("theta", 10000.0)
        case.setdefault("seed", 20260908)
        case.setdefault("max_position", 64)
        name, shape = case.get("name", ""), case.get("shape", [])
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) or name in names:
            raise ValueError("Case names must be unique simple alphanumeric names")
        names.add(name)
        if (len(shape) != 4 or any(type(n) is not int for n in shape)
                or any(not 1 <= n <= limit for n, limit in zip(shape, (128,8192,256,1024)))
                or shape[3] < 16 or shape[3] % 2):
            raise ValueError(f"Invalid public-contract shape: {shape}")
        if case["dtype"] not in ("float16", "float32"):
            raise ValueError("dtype must be float16 or float32")
        if type(case["max_position"]) is not int or not 0 <= case["max_position"] <= 131072:
            raise ValueError("max_position must be an integer in 0..131072")
        if type(case["seed"]) is not int or case["seed"] < 0:
            raise ValueError("seed must be a nonnegative integer")
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            case["theta"] = float(np.float32(case["theta"]))
        if not math.isfinite(case["theta"]) or case["theta"] <= 0:
            raise ValueError("theta must round to a positive finite FP32 value")
    # Import the existing reference functions only; do not call its build/main.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("rope_camodel_reference", references[0])
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    root = args.workdir.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    shutil.copyfile(kernel, root / "kernel.asc")
    for name in COMPONENTS:
        shutil.copyfile(HERE / name, root / name)
    (root / "data").mkdir(mode=0o700)
    kernel_sha = sha(root / "kernel.asc")
    records = []
    for case in cases:
        directory = root / "data" / case["name"]
        directory.mkdir(mode=0o700)
        shape = tuple(case["shape"])
        rng = np.random.default_rng(case["seed"])
        x = rng.uniform(-10, 10, shape).astype(case["dtype"])
        p = rng.integers(0, case["max_position"] + 1, shape[:2], dtype=np.int32)
        p.flat[0] = 0
        if p.size > 1:
            p.flat[-1] = case["max_position"]
        with np.errstate(all="ignore"):
            same_powf = reference.powf_reference(x, p, case["theta"])
            official = reference.golden_module.impl(x, p, case["theta"])
        for filename, array in (("x.bin", x), ("positions.bin", p),
                                ("golden_powf.bin", same_powf), ("golden_numpy.bin", official)):
            array.tofile(directory / filename)
        mismatch, error = reference.comparison(same_powf, official, x.dtype)
        meta = {**case, "kernel_sha256": kernel_sha, "numpy_version": np.__version__,
                "input_source": "synthetic public-contract inputs; NumPy default_rng(seed)",
                "position_pattern": "independent integers, first=0; last=max_position if size>1",
                "execution_status": "not_run", "reference_diagnostic": {
                    "same_powf_vs_numpy_mismatch_fraction": float(mismatch),
                    "max_abs_error": float(error) if math.isfinite(error) else None,
                    "pass_at_local_dtype_tolerance": bool(mismatch <= 1e-4)}}
        write_json(directory / "case.json", meta)
        records.append(meta)
    write_json(root / "data/cases.json", {"status": "inputs_and_references_only", "cases": records})
    manifest = {"kind": "CAModel preparation; kernel not compiled or executed",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "kernel_sha256": kernel_sha, "source_kernel": str(kernel),
                "reference_sources_sha256": {str(path): sha(path) for path in references},
                "python": sys.version, "numpy_version": np.__version__,
                "files_sha256": manifest_files(root)}
    write_json(root / "manifest.json", manifest)
    print(json.dumps({"workdir": str(root), "kernel_sha256": kernel_sha,
                      "cases": len(records), "kernel_executed": False}))
    return 0


def build(args):
    root = args.workdir.resolve(strict=True)
    manifest = verify(root)
    cmake = shutil.which(args.cmake)
    if not cmake:
        raise ValueError(f"CMake not found: {args.cmake}")
    build_dir = root / "build"
    build_dir.mkdir(mode=0o700, exist_ok=False)
    commands = [[cmake, "-S", str(root), "-B", str(build_dir),
                 "-DCMAKE_ASC_RUN_MODE=sim", "-DCMAKE_ASC_ARCHITECTURES=dav-2201"],
                [cmake, "--build", str(build_dir), "--parallel", str(args.jobs)]]
    report = {"kernel_sha256": manifest["kernel_sha256"], "commands": [], "status": "fail"}
    for name, command in zip(("configure", "build"), commands):
        with (root / (name + ".log")).open("x") as log:
            result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        report["commands"].append({"command": command, "exitcode": result.returncode})
        if result.returncode:
            break
    else:
        binary = build_dir / "rope_sim_runner"
        report.update(status="pass", binary_sha256=sha(binary))
    write_json(root / "build.json", report)
    print(json.dumps({"status": report["status"], "report": str(root / "build.json")}))
    return 0 if report["status"] == "pass" else 1


def run(args):
    root = args.workdir.resolve(strict=True)
    verify(root)
    # The verified profiler wrapper checks build/kernel/binary identity and makes
    # a fresh private run directory. It retains both numerical reference checks.
    return subprocess.call([sys.executable, str(root / "run_profiles.py"),
                            "--case", args.case, "--cores", str(args.cores),
                            "--profiler", args.profiler])


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    stage_parser = sub.add_parser("stage", help="Copy sources and generate inputs/references only")
    stage_parser.add_argument("--workdir", required=True, type=Path)
    stage_parser.add_argument("--kernel", required=True, type=Path)
    stage_parser.add_argument("--operator-root", type=Path, default=HERE.parents[1],
                              help="Operator directory containing tests/ and scripts/")
    stage_parser.add_argument("--cases", type=Path, help="JSON list; overrides single-case arguments")
    stage_parser.add_argument("--name", default="synthetic")
    stage_parser.add_argument("--shape", type=int, nargs=4, default=[1,9,3,32], metavar=("B","S","H","D"))
    stage_parser.add_argument("--dtype", choices=("float16", "float32"), default="float32")
    stage_parser.add_argument("--theta", type=float, default=10000.0)
    stage_parser.add_argument("--seed", type=int, default=20260908)
    stage_parser.add_argument("--max-position", type=int, default=64)
    stage_parser.set_defaults(function=stage)
    build_parser = sub.add_parser("build", help="Compile the staged kernel with installed CANN")
    build_parser.add_argument("--workdir", required=True, type=Path)
    build_parser.add_argument("--cmake", default="cmake")
    build_parser.add_argument("--jobs", type=int, choices=range(1,257), default=2, metavar="N")
    build_parser.set_defaults(function=build)
    run_parser = sub.add_parser("run", help="Profile one case and check its fresh output")
    run_parser.add_argument("--workdir", required=True, type=Path)
    run_parser.add_argument("--case", default="synthetic")
    run_parser.add_argument("--cores", type=int, choices=range(1,49), default=1, metavar="N")
    run_parser.add_argument("--profiler", default="msopprof", help="PATH name or explicit executable")
    run_parser.set_defaults(function=run)
    args = parser.parse_args()
    try:
        return args.function(args)
    except (ValueError, OSError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
