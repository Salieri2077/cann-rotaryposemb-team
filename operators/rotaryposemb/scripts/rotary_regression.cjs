// CPU-only algebra/index regression. Math.sin/cos do NOT model Ascend A2 intrinsics.
const assert = require('node:assert/strict');
const f = Math.fround;
const mul = (a, b) => f(a * b);
const add = (a, b) => f(a + b);
const sub = (a, b) => f(a - b);
let maxTrigError = 0;
let maxRotationError = 0;
let count = 0;
for (const dim of [2, 6, 16, 20, 32, 64, 96, 128, 256]) {
  for (const theta of [1, 10000, 500000, 1000000]) {
    for (let i = 0; i < dim / 2; ++i) {
      const exponent = f(f(2 * i) / f(dim));
      assert.equal(exponent, f(i / (dim / 2)));
      if (i > 0) assert.notEqual(exponent, f(i / dim));
      const inv = f(1 / f(Math.pow(f(theta), exponent)));
      for (const position of [0, 1, 3, 1023, 65503, 65504, 65505, 131071, 131072]) {
        const angle = mul(f(position), inv);
        const quarter = mul(mul(angle, 0.5), 0.5);
        assert.ok(Math.abs(quarter) <= 32768);
        assert.equal(quarter * 4, angle);
        let s = f(Math.sin(quarter));
        let c = f(Math.cos(quarter));
        for (let step = 0; step < 2; ++step) {
          const sc = mul(s, c);
          const ss = mul(s, s);
          c = sub(mul(c, c), ss);
          s = mul(sc, 2);
        }
        const refS = f(Math.sin(angle));
        const refC = f(Math.cos(angle));
        maxTrigError = Math.max(maxTrigError, Math.abs(s - refS), Math.abs(c - refC));
        const x1 = f(1.25), x2 = f(-0.75);
        const y1 = sub(mul(x1, c), mul(x2, s));
        const y2 = add(mul(x2, c), mul(x1, s));
        maxRotationError = Math.max(maxRotationError,
          Math.abs(y1 - sub(mul(x1, refC), mul(x2, refS))),
          Math.abs(y2 - add(mul(x2, refC), mul(x1, refS))));
        count++;
      }
    }
  }
}
assert.ok(maxTrigError < 1e-6, `trig error ${maxTrigError}`);
assert.ok(maxRotationError < 2e-6, `rotation error ${maxRotationError}`);

// Continuous core partitions must cover every row once, including split tokens.
for (const tokens of [1n, 7n, 31n]) {
  for (const heads of [1n, 3n, 16n]) {
    const rows = tokens * heads;
    for (const cores of [1n, 2n, 8n, 32n]) {
      let next = 0n;
      for (let block = 0n; block < cores; ++block) {
        const begin = block * rows / cores;
        const end = (block + 1n) * rows / cores;
        assert.equal(begin, next);
        for (let row = begin; row < end; ++row) {
          assert.ok(row / heads < tokens);
          for (const dim of [6n, 20n, 128n]) {
            const offset = row * dim;
            assert.equal(offset + dim / 2n + dim / 2n, (row + 1n) * dim);
          }
        }
        next = end;
      }
      assert.equal(next, rows);
    }
  }
}
const largeRow = (1n << 32n) + 3n;
const largeOffset = largeRow * 128n;
assert.ok(largeOffset > 0xffffffffn);
assert.notEqual(largeOffset, BigInt.asUintN(32, largeOffset));
assert.equal(largeOffset + 64n + 64n, (largeRow + 1n) * 128n);
console.log({ count, maxTrigError, maxRotationError, largeOffset: String(largeOffset) });
console.log('PASS: CPU FP32 algebra and index model only; no CANN compilation or NPU validation.');
