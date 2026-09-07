# 联合 Sin/Cos 数学设计与来源

## Derivation

For reduced angle r, use:
a = abs(r)
w = pi - a, evaluated with split FP32 pi
u = pi/2 - a, evaluated with split FP32 pi/2
z = a * w
sin(r) = (r * w) * P(z)
cos(r) = u * Q(z)

The exact analytic functions on z in [0, pi^2/4] are:
P(z) = cos(sqrt(pi^2/4 - z)) / z, with P(0) = 1/pi.
Q(z) = sin(sqrt(pi^2/4 - z)) / sqrt(pi^2/4 - z), with Q(pi^2/4) = 1.

Five-term P and six-term Q were generated with mpmath.chebyfit at 60 decimal digits.
All coefficients are positive. The candidate evaluates each Mul and Adds separately in FP32.
No FMA, Compare, Select, scalar per-element trig, or architecture-specific SinCos API is used.

P coefficients, highest degree first:
2.580631073747187e-7
2.1560553672307594e-5
1.160294554180584e-3
3.2251527327119334e-2
3.183098865345572e-1

Q coefficients, highest degree first:
2.3889217773452806e-8
2.457805570135570e-6
1.726966512531477e-4
6.9616269567191625e-3
1.2900613822529625e-1
6.366197723507009e-1

## Why this can improve device performance

The current official v220 implementation has 27 basic vector operations / barriers for float Sin
and 34 for float Cos, excluding API mask, shape, temporary-buffer loop and validation overhead.
The two calls repeat pi-domain reduction and reconstruct sign separately.
This candidate uses 28 basic vector operations and 17 barriers for both outputs combined.
Those are source-level counts, NOT an NPU latency claim.
The candidate reuses the seven existing angle buffers. The integrated implementation removes the unused trigTmp allocation and host scratch-size queries.

## Validation

The joint polynomial candidate passed all 230 CPU kernel model cases versus independent same-powf reference; integrated v2 also passed all 15 CANNJudge cases (submission 229487).
This includes irregular dimensions, FP16 / FP32, positions up to 131072, and theta < 1.
The pre-existing local NumPy golden diagnostic remains 107 failing cases from power-rounding differences;
that diagnostic is reported, not suppressed. See the recorded platform and CPU results in this directory.

The standalone numerical scan tested 17,000,008 FP32 angles:
- 4,000,001 uniform reduced-domain samples
- 5,000,006 random, logarithmically distributed and endpoint reduced samples
- 4,000,001 uniform raw angles in [0,131072]
- 4,000,000 random raw angles in [0,131072]

Largest measured absolute error against float64 NumPy sin/cos, including existing range reduction:
sin 2.5382067947443687e-7; cos 2.0193546490521186e-7.
No sample exceeded 3e-7.
Reduced-domain-only maxima: sin 2.1218101853293092e-7; cos 1.6213055420433164e-7.
See sincos_numeric.json and ../../tests/check_joint_sincos.py.

The existing vector reduction can occasionally produce |r| slightly above pi at quotient-rounding boundaries
(max observed 3.1528585). This candidate also remained within 3e-7 on those samples.
This is empirical coverage, not a formal all-input floating-point bound.

## API risks and validation still needed

- Integrated v2 was compiled and evaluated on CANNJudge; standalone local NPU runner remains untested.
- CPU arithmetic model does not model asynchronous pipeline hazards.
- An explicit barrier separates reading width for centered from overwriting width, avoiding a WAR hazard.
- All operations use documented count-based Abs / Muls / Adds / Mul APIs and aligned existing buffers.
- Retaining ordinary APIs avoids undocumented FMA assumptions on dav2201.
- Official SinCos is not a substitute on this target: CANN9 lists Atlas350 only and A2/A3 as unsupported.
- Do not import the official internal implementation headers; they explicitly disallow direct inclusion.

## Primary sources

Official CANN9 SinCos product support:
https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_10216.html

Official CANN9 Cos API:
https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0508.html

Official Sin implementation, exact source revision inspected:
https://gitcode.com/cann/asc-devkit/blob/0290f560c82a867528b8ecbdb1a20366a6760a64/impl/adv_api/detail/math/sin/sin_common_impl.h

Official Cos implementation:
https://gitcode.com/cann/asc-devkit/blob/0290f560c82a867528b8ecbdb1a20366a6760a64/impl/adv_api/detail/math/cos/cos_common_impl.h

Official composite-instruction performance/precision caveats:
https://asc.gitcode.com/api/SIMD-API/basic_api/memory_vector_compute/composite_compute/overview.html
Three disjoint operands in MulAddDst / FusedMulAdd create three reads and can halve theoretical parallelism;
the general docs do not promise improved precision for same-type operands.

mpmath approximation API:
https://mpmath.org/doc/current/calculus/approximation.html
