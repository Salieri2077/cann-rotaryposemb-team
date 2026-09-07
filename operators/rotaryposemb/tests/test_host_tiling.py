#!/usr/bin/env python3
"""Compile and exhaustively inspect the actual host tiling statements on CPU.

This extracts statements from kernel.asc, without duplicating their formulas.
It verifies task coverage, output block boundaries, 64-bit offsets, repeat limits,
and the declared UB allocation budget. This is not CANN compilation or an NPU test.
"""
from pathlib import Path
import subprocess
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
struct InputMetadata { const int64_t* shape; int32_t dtype; };
LaunchConfig configure(uint64_t tokens, uint32_t heads, uint32_t dim,
                       uint32_t elementBytes, int64_t availableCoreNum) {
    const int64_t b = tokens > 8192 ? 128 : 1;
    int64_t shape[] = {b, int64_t(tokens / b), heads, dim};
    InputMetadata in{shape, elementBytes == 4 ? 0 : 1};
    const float theta = 10000.0f;
    @BODY@
    return cfg;
}
uint64_t boundary(const LaunchConfig& c, uint64_t unit, uint32_t bytes) {
    if (unit >= c.workUnits) return c.tokens * c.heads * c.dim * bytes;
    if (c.batched) return unit * c.batchTokens * c.heads * c.dim * bytes;
    if (c.groups == 1) return unit * c.tokenGrain * c.heads * c.dim * bytes;
    const uint64_t token = unit / c.groups;
    const uint64_t head = (unit % c.groups) * c.headGroup;
    return (token * c.heads + head) * c.dim * bytes;
}
void verify(const LaunchConfig& c, uint32_t bytes, uint32_t cores) {
    assert(c.tokens > 0 && c.workUnits > 0 && c.blockCount > 0);
    assert(c.rowStride >= c.halfDim && c.rowStride * bytes % 32 == 0);
    assert(c.blockCount == std::min<uint64_t>(c.workUnits, cores));
    assert(c.tileElements == kSmallTileElements || c.tileElements == kHalfTileElements);
    assert(c.angleCapacity <= kMaxAngles);
    assert(c.tileElements == kSmallTileElements || c.angleCapacity <= kMaxAngles / 2);
    if (c.batched) {
        assert(c.batchTokens > 0);
        assert(c.angleCapacity == c.batchTokens * c.heads * c.rowStride);
        assert(c.angleCapacity <= c.tileElements);
    } else {
        assert(c.tokenGrain > 0 && c.headGroup > 0 && c.groups > 0);
        assert(c.tileHeads > 0 && c.tileHeads <= kMaxHeadRepeats && c.tileHeads <= 255);
        assert(c.tileHeads * c.rowStride <= c.tileElements);
        assert(c.groups == (c.heads + c.headGroup - 1) / c.headGroup);
        assert(c.groups == 1 || (c.tokenGrain == 1 && c.dim * bytes % 32 == 0));
    }
    // Mirrors only the allocation *accounting*: values come from actual host cfg.
    const uint64_t fpWorkBytes = bytes == 4 ? 32ull : 4ull * c.tileElements * 4;
    const uint64_t ub = 8ull * c.tileElements * bytes + kPositionCache * 4ull
        + fpWorkBytes + c.tileElements * 4ull
        + c.rowStride * 4ull + 7ull * c.angleCapacity * 4;
    assert(ub <= 192 * 1024);
    const uint64_t per = (c.workUnits + c.blockCount - 1) / c.blockCount;
    uint64_t endByte = 0;
    for (uint32_t block = 0; block < c.blockCount; ++block) {
        const uint64_t begin = std::min<uint64_t>(block * per, c.workUnits);
        const uint64_t end = std::min<uint64_t>((block + 1) * per, c.workUnits);
        const uint64_t firstByte = boundary(c, begin, bytes);
        const uint64_t lastByte = boundary(c, end, bytes);
        assert(firstByte == endByte && lastByte >= firstByte);
        // Every live split between two cores lands on a 32-byte boundary.
        if (begin > 0 && begin < c.workUnits) assert(firstByte % 32 == 0);
        endByte = lastByte;
    }
    assert(endByte == c.tokens * c.heads * c.dim * bytes);
}
int main() {
    uint64_t checked = 0;
    const uint64_t tokens[] = {1, 3, 7, 33, 65, 129, 1048576};
    for (uint32_t bytes : {2u, 4u}) {
        for (uint32_t dim = 16; dim <= 1024; dim += 2) {
            for (uint32_t heads = 1; heads <= 256; ++heads) {
                for (uint64_t t : tokens) {
                    const auto c = configure(t, heads, dim, bytes, 32);
                    verify(c, bytes, 32);
                    ++checked;
                }
            }
        }
    }
    for (uint32_t cores : {1u, 8u, 64u, 65535u}) {
        for (uint64_t t : tokens) {
            for (uint32_t dim : {16u, 18u, 24u, 30u, 66u, 1022u, 1024u}) {
                for (uint32_t heads : {1u, 3u, 4u, 5u, 127u, 256u}) {
                    for (uint32_t bytes : {2u, 4u}) {
                        verify(configure(t, heads, dim, bytes, cores), bytes, cores);
                        ++checked;
                    }
                }
            }
        }
    }
    const auto largest = configure(1048576, 256, 1024, 4, 32);
    assert(boundary(largest, largest.workUnits, 4) == (1ull << 40));
    std::printf("Launch bytes: %zu / 1536\n", sizeof(LaunchConfig) + 3 * sizeof(uint64_t));
    std::printf("PASS: %llu host configurations; all even D=16..1024, H=1..256; "
                "32-byte core boundaries, full task coverage, UB <= 192 KiB, 1 TiB offsets.\n",
                static_cast<unsigned long long>(checked));
    std::puts("CPU host logic only; CANN compilation, device memory hazards and performance remain untested.");
}
"""

def main():
    source = (ROOT / "kernel.asc").read_text()
    constants = "\n".join(re.findall(r"^constexpr uint32_t k\w+ = [^;]+;", source, re.MULTILINE))
    declarations = "struct LaunchConfig" + source.split("struct LaunchConfig", 1)[1].split("template<class T>", 1)[0]
    preamble = constants + "\n" + declarations
    body = source.split("    LaunchConfig cfg{};", 1)[1].split("    // Match the reference", 1)[0]
    body = "    LaunchConfig cfg{};" + body
    if "cfg.blockCount" not in body or "cfg.invFreq" in body:
        raise RuntimeError("Host tiling boundaries changed; review this extraction adapter")
    code = "#include <algorithm>\n#include <cassert>\n#include <cstdint>\n#include <cstdio>\n" + preamble + HARNESS.replace("@BODY@", body)
    with tempfile.TemporaryDirectory(prefix="rope_host_tiling_") as directory:
        directory = Path(directory)
        source_file, executable = directory / "tiling.cpp", directory / "tiling"
        source_file.write_text(code)
        subprocess.run(["g++", "-O2", "-std=c++14", "-Wall", "-Wextra",
                        str(source_file), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)

if __name__ == "__main__":
    main()
