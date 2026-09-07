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
    sim::forcedLaunches=0; sim::tinyLaunches=0;
    sim::gmInCalls=sim::gmOutCalls=sim::gmInBytes=sim::gmOutBytes=0;
    sim::tbufInitCalls=sim::tqueInitCalls=0;
    for(unsigned i=0;i<6;++i) sim::eventSets[i]=sim::eventWaits[i]=0;
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

extern "C" uint32_t sim_forced_count() { return sim::forcedLaunches; }

extern "C" uint32_t sim_tiny_count() { return sim::tinyLaunches; }
extern "C" void sim_tiny_stats(uint64_t* output) {
    output[0]=sim::gmInCalls;output[1]=sim::gmOutCalls;
    output[2]=sim::gmInBytes;output[3]=sim::gmOutBytes;
    output[4]=sim::tbufInitCalls;output[5]=sim::tqueInitCalls;
    for(unsigned i=0;i<6;++i) { output[6+i]=sim::eventSets[i];output[12+i]=sim::eventWaits[i]; }
}
