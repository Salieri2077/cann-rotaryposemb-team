#!/usr/bin/env python3
"""Profile one stored case with CAModel, then compare its fresh output with both references.

Configurable requested core count and one launch; internal timeout two minutes, outer timeout 180 seconds.
Simulation timings are not hardware measurements. --help does not run a model.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
BINARY = BUILD / "rope_sim_runner"



def run_logged(command, cwd, log_path, timeout):
    started = time.monotonic()
    record = {"command": command, "log": str(log_path), "timeout_seconds": timeout,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "timed_out": False}
    with log_path.open("w") as log:
        process = subprocess.Popen(command, cwd=cwd, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            if isinstance(error, KeyboardInterrupt):
                raise
            record["timed_out"] = True
    record.update(exitcode=process.returncode, wall_seconds=time.monotonic() - started)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="low_h_generic", metavar="NAME",
                        help="Name in data/cases.json, e.g. official_case0 or low_h_pipeline")
    parser.add_argument("--cores", type=int, default=1)
    parser.add_argument("--profiler", default="msopprof", help="Executable name on PATH or explicit path")
    args = parser.parse_args()
    profiler_name = shutil.which(args.profiler)
    if not profiler_name:
        parser.error(f"Profiler not found: {args.profiler}; source CANN set_env.sh")
    profiler = Path(profiler_name).resolve()
    if not 1 <= args.cores <= 48:
        parser.error("--cores must be 1..48 for this model")
    cases = json.loads((ROOT / "data/cases.json").read_text())["cases"]
    matches = [item for item in cases if item["name"] == args.case]
    if len(matches) != 1:
        parser.error("Choose one manifest case: " + ", ".join(item["name"] for item in cases))
    meta = matches[0]
    # official_case0 is stored in data/case0; resolve names from actual metadata.
    directories = [path.parent for path in (ROOT / "data").glob("*/case.json")
                   if json.loads(path.read_text())["name"] == args.case]
    if len(directories) != 1:
        parser.error(f"Cannot resolve a unique case directory for {args.case}")
    source = directories[0]
    stored = json.loads((source / "case.json").read_text())
    if any(stored[key] != meta[key] for key in ("shape", "dtype", "theta")):
        parser.error("Case metadata and manifest disagree")
    for executable in (BINARY, profiler):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            parser.error(f"Executable missing: {executable}; source CANN set_env.sh and build the runner")
    os.umask(0o077)
    # msopprof rejects group/other-writable binaries and output parents.
    for path in (BUILD, BINARY):
        if path.stat().st_mode & 0o022:
            parser.error(f"Group/other-writable build path rejected by msopprof: {path}")
    output_root = ROOT / "profiles"
    output_root.mkdir(mode=0o700, exist_ok=True)
    output_root.chmod(0o700)
    run_dir = Path(tempfile.mkdtemp(prefix=args.case + f"-c{args.cores}-", dir=output_root))
    run_dir.chmod(0o700)
    case_dir, profile_dir, work_dir = (run_dir / name for name in ("case", "profile", "work"))
    for directory in (case_dir, profile_dir, work_dir):
        directory.mkdir(mode=0o700)
    # Original data/y.bin and comparison.json remain untouched; no stale output is copied.
    for name in ("x.bin", "positions.bin", "golden_powf.bin", "golden_numpy.bin", "case.json"):
        shutil.copyfile(source / name, case_dir / name)
    kernel_sha = hashlib.sha256((ROOT / "kernel.asc").read_bytes()).hexdigest()
    build_manifest = json.loads((ROOT / "build.json").read_text())
    if (build_manifest.get("status") != "pass" or build_manifest.get("kernel_sha256") != kernel_sha
            or build_manifest.get("binary_sha256") != hashlib.sha256(BINARY.read_bytes()).hexdigest()):
        parser.error("Build manifest does not match kernel/binary; stage a new work directory")
    run_meta = json.loads((case_dir / "case.json").read_text())
    run_meta["reference_generation_kernel_sha256"] = run_meta.get("kernel_sha256")
    run_meta["kernel_sha256"] = kernel_sha
    (case_dir / "case.json").write_text(json.dumps(run_meta, indent=2) + "\n")
    report = {"case": args.case, "shape": meta["shape"], "dtype": meta["dtype"],
              "theta": meta["theta"], "seed": meta.get("seed"), "source_case": str(source),
              "run_directory": str(run_dir), "kernel_sha256": kernel_sha,
              "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(),
              "requested_vector_cores": args.cores, "launch_count": 1,
              "timing_scope": "Official CAModel simulation; not hardware or CANNJudge latency"}
    command = [str(profiler), "simulator", "--soc-version=Ascend910B1",
               "--aic-metrics=PipeUtilization,ResourceConflictRatio", "--launch-count=1",
               "--timeout=2", f"--output={profile_dir}", str(BINARY), str(case_dir),
               *map(str, meta["shape"]), meta["dtype"], str(meta["theta"]), str(args.cores), "1", "0"]
    print(f"Profiling {args.case}; output: {run_dir}", flush=True)
    report["profiler"] = run_logged(command, work_dir, run_dir / "profiler.log", 180)
    report["runner_metadata"] = None
    for line in (run_dir / "profiler.log").read_text(errors="replace").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("mode") == "sim":
            report["runner_metadata"] = item
    reported = report["runner_metadata"] or {}
    report["runner_identity_verified"] = (
        reported.get("kernel_sha256") == kernel_sha
        and reported.get("requested_vector_cores") == args.cores and reported.get("iterations") == 1)
    report["trace_paths"] = sorted(str(path) for path in profile_dir.rglob("trace.json"))
    report["instruction_csv_paths"] = sorted(str(path) for path in profile_dir.rglob("*_instr_exe.csv"))
    report["source_csv_paths"] = sorted(str(path) for path in profile_dir.rglob("*_code_exe.csv"))
    report["visualize_data_paths"] = sorted(str(path) for path in profile_dir.rglob("visualize_data.bin"))
    report["numerical_check"] = {"status": "not_run", "exitcode": None}
    profile_ok = report["profiler"]["exitcode"] == 0 and not report["profiler"]["timed_out"]
    if profile_ok and (case_dir / "y.bin").is_file():
        check = run_logged([sys.executable, str(ROOT / "check_output.py"), str(case_dir)],
                           work_dir, run_dir / "check_output.log", 30)
        check["status"] = "pass" if check["exitcode"] == 0 and not check["timed_out"] else "fail"
        comparison = case_dir / "comparison.json"
        check["comparison_path"] = str(comparison) if comparison.is_file() else None
        if comparison.is_file():
            check["comparison"] = json.loads(comparison.read_text())
        report["numerical_check"] = check
    else:
        report["numerical_check"]["reason"] = "Profiler failed/timed out or no fresh y.bin"
    passed = (profile_ok and report["runner_identity_verified"] and bool(report["trace_paths"])
              and report["numerical_check"]["status"] == "pass")
    report["status"] = "pass" if passed else "fail"
    report_path = run_dir / "result.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "profiler_exitcode": report["profiler"]["exitcode"],
                      "numerical_check": report["numerical_check"]["status"], "report": str(report_path)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
