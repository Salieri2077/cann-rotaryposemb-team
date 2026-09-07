"""Exercise expanded medium-head batching, boundaries, and safe coefficient schedules."""
import json
import numpy as np
from run_cpu_kernel import build, powf_reference, comparison
run, _ = build()
rng = np.random.default_rng(20260909)
records = []
shapes = [(1,17,5,1024), (1,17,5,994), (1,17,5,1010),
          (1,129,128,64), (1,65,128,128),
          (1,257,256,32), (1,257,129,32), (1,257,256,16)]
for dtype in (np.float32, np.float16):
    for shape in shapes:
        x = rng.uniform(-10, 10, shape).astype(dtype)
        p = rng.integers(0, 131073, shape[:2], dtype=np.int32)
        p.flat[0] = 131072
        for cores in (1, 8, 32):
            for theta in (10000., .5):
                y = np.full(shape, np.nan, dtype=dtype)
                status = run(x.ctypes.data, p.ctypes.data, y.ctypes.data,
                             *shape, int(dtype == np.float16), cores, theta)
                assert status == 0, (shape, dtype, cores, theta, status)
                mismatch, error = comparison(y, powf_reference(x, p, theta), dtype)
                assert mismatch <= 1e-4, (shape, dtype, cores, theta, mismatch, error)
                records.append(dict(shape=shape, dtype=np.dtype(dtype).name,
                    cores=cores, theta=theta, mismatch=mismatch, max_error=error))
print(f"PASS {len(records)}/{len(records)} max-UB1536, D994/1010/1024 and repeat-capped-tile cases")
