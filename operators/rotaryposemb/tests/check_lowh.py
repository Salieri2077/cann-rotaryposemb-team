"""Additional low-head compact-trig expansion cases."""
import json
import numpy as np
from run_cpu_kernel import build, powf_reference, comparison

# Verify every stage keeps all still-needed source rows intact. This is
# independent of the synchronous CPU model, which cannot detect pipeline WAR.
for heads in (2, 3, 4):
    for tokens in range(1, 257):
        data = list(range(tokens)) + [-1] * (tokens * heads - tokens)
        pending = tokens
        while pending > 1:
            begin = (pending + heads - 1) // heads
            reads = set(range(begin, pending))
            writes = set(range(begin * heads, pending * heads))
            assert reads.isdisjoint(writes)
            assert min(writes) >= pending
            for token in range(pending - 1, begin - 1, -1):
                value = data[token]
                assert value == token
                for h in range(heads):
                    data[token * heads + h] = value
            pending = begin
        for h in range(1, heads):
            data[h] = data[0]
        assert data == [t for t in range(tokens) for _ in range(heads)]
print('PASS 768 independent expansion schedules, with per-stage nonoverlap')

run, _ = build()
rng = np.random.default_rng(20260908)
records = []
shapes = [(1, 257, 2, 16), (1, 171, 3, 16), (1, 129, 4, 16),
          (1, 257, 2, 18), (1, 257, 3, 18), (1, 257, 4, 18),
          (1, 7, 2, 1024), (1, 7, 3, 1024), (1, 7, 4, 1024),
          (1, 1, 2, 32), (1, 1, 3, 32), (1, 1, 4, 32)]
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
print(f'PASS {len(records)}/{len(records)} low-H aligned/unaligned, large-batch, batch-tail and multicore cases')
