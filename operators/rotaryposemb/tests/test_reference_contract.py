#!/usr/bin/env python3
"""CPU contract tests for the unmodified official golden; these do not run kernel.asc."""
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("official_rope", ROOT / "scripts/RotaryPosEmb.py")
golden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(golden)

class ReferenceContract(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(1234)

    def test_zero_position_identity(self):
        for dtype in (np.float16, np.float32):
            x = self.rng.normal(size=(2, 3, 5, 24)).astype(dtype)
            np.testing.assert_array_equal(golden.impl(x, np.zeros((2, 3), np.int32)), x)

    def test_rotate_half_pairs_are_not_adjacent(self):
        # theta=1 makes every frequency exactly one, isolating the pairing rule.
        x = np.arange(16, dtype=np.float32).reshape(1, 1, 1, 16)
        output = golden.impl(x, np.array([[1]], np.int32), theta=1.0).reshape(-1)
        c, s = np.cos(np.float32(1)), np.sin(np.float32(1))
        for i in range(8):
            self.assertAlmostEqual(float(output[i]), float(np.float32(i) * c - np.float32(i + 8) * s), places=6)
            self.assertAlmostEqual(float(output[i + 8]), float(np.float32(i + 8) * c + np.float32(i) * s), places=6)

    def test_output_shape_and_dtype_with_non_aligned_dimensions(self):
        for dtype in (np.float16, np.float32):
            for dim in (16, 18, 20, 24, 30, 66, 510, 1022, 1024):
                shape = (2, 3, 7, dim)
                x = self.rng.normal(size=shape).astype(dtype)
                y = golden.impl(x, np.array([[0, 1, 131072], [123, 999, 65000]], np.int32))
                self.assertEqual(y.shape, shape)
                self.assertEqual(y.dtype, np.dtype(dtype))
                self.assertTrue(np.isfinite(y).all())

    def test_head_broadcast(self):
        x = self.rng.normal(size=(1, 4, 1, 66)).astype(np.float32)
        positions = np.array([[0, 17, 131071, 131072]], np.int32)
        expected = np.repeat(golden.impl(x, positions), 127, axis=2)
        np.testing.assert_array_equal(golden.impl(np.repeat(x, 127, axis=2), positions), expected)

    def test_positions_follow_tokens_and_batch(self):
        x = self.rng.normal(size=(3, 7, 5, 30)).astype(np.float32)
        positions = self.rng.integers(0, 131073, (3, 7), dtype=np.int32)
        y = golden.impl(x, positions)
        order = np.array([6, 2, 4, 0, 1, 5, 3])
        np.testing.assert_array_equal(golden.impl(x[:, order], positions[:, order]), y[:, order])
        for b in range(3):
            for s in range(7):
                np.testing.assert_array_equal(golden.impl(x[b:b+1, s:s+1], positions[b:b+1, s:s+1]), y[b:b+1, s:s+1])

    def test_pair_norm_is_preserved(self):
        x = self.rng.normal(size=(2, 5, 3, 1024)).astype(np.float32)
        p = self.rng.integers(0, 131073, (2, 5), dtype=np.int32)
        y = golden.impl(x, p)
        before = x[..., :512] ** 2 + x[..., 512:] ** 2
        after = y[..., :512] ** 2 + y[..., 512:] ** 2
        np.testing.assert_allclose(after, before, rtol=5e-7, atol=1e-6)

    def test_float16_uses_float32_internal_math(self):
        x = self.rng.uniform(-10, 10, (1, 9, 3, 24)).astype(np.float16)
        p = np.array([[0, 1, 2, 7, 4096, 32768, 65536, 131071, 131072]], np.int32)
        np.testing.assert_array_equal(golden.impl(x, p), golden.impl(x.astype(np.float32), p).astype(np.float16))

    def test_non_default_theta(self):
        x = self.rng.normal(size=(1, 3, 2, 24)).astype(np.float32)
        p = np.array([[1, 1000, 131072]], np.int32)
        default = golden.impl(x, p)
        for theta in (0.5, 1e-6, 1.0, 1000.0, 1000000.0):
            y = golden.impl(x, p, theta)
            self.assertTrue(np.isfinite(y).all())
            self.assertFalse(np.allclose(y, default))

    def test_input_is_not_modified(self):
        x = self.rng.normal(size=(1, 3, 4, 24)).astype(np.float32)
        p = np.array([[0, 1, 131072]], np.int32)
        old_x, old_p = x.copy(), p.copy()
        golden.impl(x, p)
        np.testing.assert_array_equal(x, old_x)
        np.testing.assert_array_equal(p, old_p)

    def test_special_values_obey_reference_operation_order(self):
        x = np.ones((1, 1, 1, 16), np.float32)
        x[..., 0] = np.nan
        x[..., 1] = np.inf
        with np.errstate(invalid="ignore"):
            y = golden.impl(x, np.array([[0]], np.int32), theta=1.0)
        self.assertTrue(np.isnan(y[..., 0]).all())
        self.assertTrue(np.isnan(y[..., 8]).all())
        self.assertTrue(np.isposinf(y[..., 1]).all())
        self.assertTrue(np.isnan(y[..., 9]).all())

if __name__ == "__main__":
    unittest.main(verbosity=2)
