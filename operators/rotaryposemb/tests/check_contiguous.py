"""Stress the continuous-row DMA branch and its strided arithmetic."""
import json
import numpy as np
from run_cpu_kernel import build, powf_reference, comparison

run, _ = build()
rng = np.random.default_rng(20260907)
records = []
shapes = [(1, 9, 129, 32), (1, 17, 127, 64), (1, 3, 256, 128),
          (1, 7, 33, 256), (1, 5, 17, 768), (1, 3, 31, 1024),
          (1, 1, 255, 512), (1, 9, 9, 48)]
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
print(f'PASS {len(records)}/{len(records)} additional high-H aligned, partial-tile and multi-core cases')
