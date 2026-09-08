# RotaryPosEmb CAModel reproduction

This tool copies a chosen `kernel.asc` into a new work directory, generates
synthetic inputs and two references, builds the existing ASC runner, and invokes
the official CANN simulator profiler. It does not install CANN or use a real NPU.
The runner/CMake and profiler invocation originate from the locally validated
CANN 9.0.0 `dav-2201`/`Ascend910B1` workflow.

Requirements:
Linux x86_64, Python with NumPy, CMake, and a CANN installation containing ASC
(`bisheng`), CAModel libraries, and `msopprof`. Source that installation's
`set_env.sh` first. If `msopprof` is absent from PATH, pass its executable using
`--profiler`. The Python environment used to stage and run must have NumPy.

From the operator directory (containing `kernel.asc`, `tests/`, and `scripts/`):

```sh
# Replace this path with your installed CANN environment script.
source /opt/ascend/cann-9.0.0/set_env.sh

python tools/camodel/stage.py stage \
  --kernel kernel.asc --workdir /tmp/rope-camodel-example \
  --name synthetic --shape 1 9 3 32 --dtype float32 \
  --theta 10000 --seed 20260908 --max-position 64
python tools/camodel/stage.py build --workdir /tmp/rope-camodel-example --jobs 2
python tools/camodel/stage.py run --workdir /tmp/rope-camodel-example --cores 1
python tools/camodel/stage.py run --workdir /tmp/rope-camodel-example --cores 32
```

When the tools have not yet been placed inside the operator directory, add
`--operator-root /path/to/operators/rotaryposemb` to `stage`. Any chosen kernel
can be staged independently using `--kernel /path/to/candidate/kernel.asc`.
Do not edit staged files: their hashes are checked before build/run. Staging and
building refuse an existing destination; use a new work directory after a failed
build or a source change. Every run creates a unique private directory under
`WORKDIR/profiles/`, so repeated runs preserve prior outputs.

For multiple cases, pass `stage --cases cases.json`; the JSON list replaces the
single-case arguments. Each case requires a unique name and `[B,S,H,D]` shape:

```json
[
  {"name":"small", "shape":[1,9,3,32], "dtype":"float32", "theta":10000,
   "seed":20260908, "max_position":64},
  {"name":"wide_angle", "shape":[1,7,3,18], "dtype":"float16", "theta":0.5,
   "seed":20260909, "max_position":131072}
]
```

Select one with `run --case small --cores 1`. Positions are independent random
integers in `[0,max_position]`, with the first position set to zero and the last
set to `max_position` when there is more than one token. X is uniform in
`[-10,10]` then cast to the chosen dtype. Theta is rounded to FP32 before both
reference generation and runner invocation. These are constructed cases, with
no claim to match hidden judge inputs. Large legal shapes can consume substantial
CPU memory and simulator time; start with small cases.

`stage` imports the existing `tests/run_cpu_kernel.py` only to call
`powf_reference`, `golden_module.impl`, and `comparison`. It does not execute its
CPU kernel model. `manifest.json` records kernel, staged files, source reference
hashes, and Python/NumPy versions. `build.json` records commands, status, and the
built binary hash; `configure.log` and `build.log` retain compiler output.

Each profile `result.json` retains the executed command, exit status, timeout,
runner-reported kernel identity, raw trace/CSV paths, and both numerical checks.
The runner executes one launch with the requested number of vector cores, up to
the model's 48-core limit. The command uses `msopprof simulator`,
`--soc-version=Ascend910B1`, and `PipeUtilization,ResourceConflictRatio`. Internal
profiler timeout is two minutes; the wrapper kills the process group after 180
seconds. Very large cases can time out and remain recorded as failures.

Both stored references must pass: same host `powf` frequency construction and
the official NumPy implementation. The unchanged local checks use `rtol=atol`
of `1e-4` for FP32 or `1e-3` for FP16, `equal_nan=True`, and maximum mismatch
fraction `1e-4`. A discrepancy between references is recorded at staging and is
never used to waive a failure. A run also fails if the profiler fails, fresh
output or trace is missing, or the runner's kernel hash/core count does not
match. `check_output.py CASE_DIR` can compare a separately obtained `y.bin` but
refuses to overwrite an existing `comparison.json`.

CAModel results are simulation evidence. The runner's
`simulation_host_batch_average_us` is host wall time including simulation;
trace durations describe the model. Neither is physical NPU timing or an online
judge score. Compare simulated cases using identical input hashes, core counts,
compiler/CANN settings, and profiling metrics, then validate performance on
hardware separately.
