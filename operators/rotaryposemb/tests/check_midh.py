"""Exercise expanded medium-head batching, boundaries, and safe coefficient schedules."""
import json
import numpy as np
from run_cpu_kernel import build, powf_reference, comparison
run, _ = build()
rng = np.random.default_rng(20260909)
records = []
shapes = [(1, 257, h, d) for h in (5, 8, 12, 16) for d in (16, 18, 64, 128)]
shapes += [(1, 257, 8, 254), (1, 257, 8, 256), (1, 257, 8, 258),
           (1, 63, 16, 64), (1, 64, 16, 64), (1, 65, 16, 64),
           (1, 257, 17, 64), (1, 1, 256, 16)]
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
for heads in range(2, 17):
    for tokens in range(1, 257):
        data = list(range(tokens)) + [-1] * (tokens * heads - tokens)
        pending = tokens
        while pending > 1:
            begin = (pending + heads - 1) // heads
            reads = set(range(begin, pending))
            writes = set(range(begin * heads, pending * heads))
            assert reads.isdisjoint(writes)
            for token in range(pending - 1, begin - 1, -1):
                value = data[token]
                assert value == token
                for h in range(heads):
                    data[token * heads + h] = value
            pending = begin
        for h in range(1, heads):
            data[h] = data[0]
        assert data == [t for t in range(tokens) for _ in range(heads)]
print(f"PASS {len(records)}/{len(records)} medium-H cases and 3840 nonoverlap schedules")
