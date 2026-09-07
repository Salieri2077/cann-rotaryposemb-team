# Exact-product Axpy reduction

One local change: replace the first two Cody-Waite Mul/Sub pairs with in-place Axpy. Polynomial coefficients, third-stage rounding, FP32 evaluation, input semantics and tolerance are unchanged.

The final combined kernel and submission identity are recorded in README.md and experiments.json. This proof concerns only the reduction change.

## Arithmetic argument

For theta>=1, inverse frequencies lie in [0,1] and positions<=131072, hence raw angles lie in [0,131072]. The rounded quotient q is an integer in [0,20861].

The first constant equals 201/32. Its largest integer numerator is 201*20861 = 4193061 < 2^22.

The second constant equals 507/2^18. Its largest integer numerator is 507*20861 = 10576527 < 2^24.

Every product therefore fits exactly in the 24-significand-bit FP32 format, including its power-of-two scaling. Fused multiply-add and separate multiplication/subtraction produce identical rounded FP32 results for these two stages. The third constant does not have this property, so its multiplication and subtraction remain separate.

The official [CANN 9 Axpy API](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0063.html) supports float operands on A2/A3 and computes dst += src * scalar. Official [composite-operation guidance](https://asc.gitcode.com/api/SIMD-API/basic_api/memory_vector_compute/composite_compute/overview.html) warns that compound operations generally differ in precision; the exact-product argument above is why this restricted replacement is valid. This is our arithmetic inference, not a blanket claim about arbitrary Axpy inputs.

## Buffers and dependencies

The raw angle slot becomes the reduced-angle slot. The original reduced slot becomes absAngle. All seven existing allocations retain their sizes and lifetimes. For theta<1, the scalar Payne-Hanek loop reads and writes each angle slot in place, then the same existing scalar/vector synchronization precedes vector use.

The third product and first Axpy only read the quotient and write disjoint buffers. A V barrier precedes the second Axpy; another precedes final subtraction. The polynomial then uses exactly the old FP32 expression and dependency sequence. No synchronization with an actual data dependency is removed.

Fast FinishTrig source counts change from 37 to 35 arithmetic API calls and 24 to 23 V barriers. This is a source-count comparison, not a hardware speedup prediction. Launch arguments and UB storage do not change.

## Validation

- 902 actual-kernel CPU model cases passed: 230 standard, 96 continuous, 144 low-H, 288 medium-H, 144 window boundary.
- The Axpy CPU model uses std::fma, so fusion is explicitly exercised.
- All 20862 possible quotient values were checked: both FP32 products equal the exact FP64 products.
- 8000001 raw angles compared the first and second fused stages bitwise to the old separate stages; no differences.
- Full 17000008-angle scan retained sin max error 2.5382067947443687e-7 and cos max error 2.0193546490521186e-7; zero samples exceeded the existing 3e-7 bound.
- Existing NumPy power diagnostic remains 107/230 mismatches; same-powf checks passed.
- CANN compilation, device asynchronous execution, hardware denormal details and timing require platform validation.
