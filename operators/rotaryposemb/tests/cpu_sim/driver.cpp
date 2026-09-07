#include "kernel_operator.h"
#include <cstdio>
struct TensorInfo { const int64_t* shape; int64_t numDims; int32_t dtype; };
struct TensorGroupInfo { const TensorInfo* tensors; int64_t numTensors; };
#include "kernel_cpu.inc"
extern "C" int sim_run(void* x, void* p, void* y, int64_t b, int64_t s, int64_t h,
                     int64_t d, int32_t dtype, int64_t cores, float theta) {
    int64_t shape[]={b,s,h,d}, pshape[]={b,s};
    TensorInfo xi={shape,4,dtype},pi={pshape,2,5},yi={shape,4,dtype};
    TensorGroupInfo xg={&xi,1},pg={&pi,1},yg={&yi,1};
    const size_t bytes=b*s*h*d*(dtype==0?4:2);
    sim::regions={{(uint8_t*)x,bytes},{(uint8_t*)p,size_t(b*s*4)},{(uint8_t*)y,bytes}};
    sim::launches=0;
    try {
        run_kernel((GM_ADDR)x,xg,(GM_ADDR)p,pg,(GM_ADDR)y,yg,cores,nullptr,theta);
        if (sim::launches != 1) throw std::runtime_error("Expected exactly one kernel launch");
        return 0;
    } catch(const std::exception& e) {
        std::fprintf(stderr,"CPU SIM: %s\n",e.what()); return -1;
    }
}

extern "C" void sim_reduce(const float* input, float* output, uint32_t count) {
    for (uint32_t i=0; i<count; ++i)
        output[i]=rope_draft::ReduceAnglePayneHanek(input[i]);
}
