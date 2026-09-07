// Synchronous CPU model of the API subset used by kernel.asc.
// This is NOT a CANN compiler, hardware simulator, or timing model.
#pragma once
#include <cstdint>
#include <cstddef>
#include <cmath>
#include <memory>
#include <vector>
#include <deque>
#include <stdexcept>
#include <cstring>
#include <algorithm>
#define __aicore__
#define __global__
#define __vector__
#define __gm__
using GM_ADDR = uint8_t*;
using aclrtStream = void*;
using half = _Float16;
namespace sim {
inline uint32_t block = 0;
inline uint32_t launches = 0;
inline uint32_t forcedLaunches = 0;
inline uint32_t tinyLaunches = 0;
inline uint64_t gmInCalls = 0, gmOutCalls = 0, gmInBytes = 0, gmOutBytes = 0;
inline uint64_t tbufInitCalls = 0, tqueInitCalls = 0;
inline uint64_t eventSets[7]{}, eventWaits[7]{};
struct Region { uint8_t* start; size_t size; };
inline std::vector<Region> regions;
inline void checkGlobal(void* ptr, size_t bytes) {
    auto p = reinterpret_cast<uintptr_t>(ptr);
    for (const auto& r : regions) {
        auto start = reinterpret_cast<uintptr_t>(r.start);
        if (p >= start && p - start <= r.size && bytes <= r.size - (p - start)) return;
    }
    throw std::runtime_error("GM transfer outside registered tensor");
}
}
namespace AscendC {
enum class TPosition { VECIN, VECOUT, VECCALC };
using QuePosition = TPosition;
enum class HardEvent { S_V, MTE2_S, V_S, MTE2_V, V_MTE3, MTE3_S, S_MTE2 };
using event_t = int;
enum pipe_t { PIPE_V, PIPE_ALL };
template<pipe_t> inline void PipeBarrier() {}
template<HardEvent E> inline void SetFlag(event_t) { ++sim::eventSets[static_cast<unsigned>(E)]; }
template<HardEvent E> inline void WaitFlag(event_t) { ++sim::eventWaits[static_cast<unsigned>(E)]; }
inline uint32_t GetBlockIdx() { return sim::block; }
enum class RoundMode { CAST_NONE, CAST_RINT };
struct Buffer { std::vector<uint8_t> bytes; explicit Buffer(size_t n): bytes(n, 0xa5) {} };
template<class T> struct LocalTensor {
    std::shared_ptr<Buffer> storage;
    size_t offset = 0;
    T* data(size_t index = 0) const {
        if (!storage || offset + (index + 1) * sizeof(T) > storage->bytes.size())
            throw std::runtime_error("UB access out of bounds");
        return reinterpret_cast<T*>(storage->bytes.data() + offset) + index;
    }
    LocalTensor operator[](size_t index) const { return {storage, offset + index * sizeof(T)}; }
    T GetValue(size_t index) const { return *data(index); }
    void SetValue(size_t index, T value) const { *data(index) = value; }
    template<class U> LocalTensor<U> ReinterpretCast() const { return {storage, offset}; }
};
template<class T> struct GlobalTensor {
    T* ptr = nullptr;
    void SetGlobalBuffer(T* p) { ptr = p; }
    GlobalTensor operator[](uint64_t offset) const { return {ptr + offset}; }
};
template<TPosition> struct TBuf {
    std::shared_ptr<Buffer> storage;
    template<class T> LocalTensor<T> Get() { return {storage, 0}; }
};
template<TPosition, int depth> struct TQue {
    std::vector<std::shared_ptr<Buffer>> buffers;
    std::vector<bool> allocated;
    std::deque<std::shared_ptr<Buffer>> queue;
    template<class T> LocalTensor<T> AllocTensor() {
        for (size_t i=0; i<buffers.size(); ++i)
            if (!allocated[i]) { allocated[i]=true; return {buffers[i],0}; }
        throw std::runtime_error("TQue exhausted");
    }
    template<class T> void EnQue(LocalTensor<T> t) {
        if (queue.size() >= depth) throw std::runtime_error("TQue depth exceeded");
        queue.push_back(t.storage);
    }
    template<class T> LocalTensor<T> DeQue() {
        if (queue.empty()) throw std::runtime_error("DeQue empty");
        auto b=queue.front(); queue.pop_front(); return {b,0};
    }
    template<class T> void FreeTensor(LocalTensor<T> t) {
        for (size_t i=0;i<buffers.size();++i) if(buffers[i]==t.storage) {
            if(!allocated[i]) throw std::runtime_error("double free queue");
            allocated[i]=false; return;
        }
        throw std::runtime_error("free foreign buffer");
    }
};
struct TPipe {
    size_t used = 0;
    void account(size_t n) { used+=n; if(used>192*1024) throw std::runtime_error("UB >192 KiB"); }
    template<TPosition P> void InitBuffer(TBuf<P>& b, size_t bytes) {
        ++sim::tbufInitCalls; account(bytes); b.storage=std::make_shared<Buffer>(bytes);
    }
    template<TPosition P,int D> void InitBuffer(TQue<P,D>& q,int num,size_t bytes) {
        ++sim::tqueInitCalls; account(num*bytes); q.allocated.resize(num,false);
        for(int i=0;i<num;++i) q.buffers.push_back(std::make_shared<Buffer>(bytes));
    }
    event_t FetchEventID(HardEvent) { return 0; }
};
struct DataCopyExtParams {
    uint16_t blockCount;
    uint32_t blockLen, srcStride, dstStride, rsv;
};
template<class T> struct DataCopyPadExtParams {
    bool isPad; uint8_t leftPadding,rightPadding; T paddingValue;
};
template<class T> void DataCopyPad(LocalTensor<T> dst,GlobalTensor<T> src,
        const DataCopyExtParams& cp,const DataCopyPadExtParams<T>& pad) {
    ++sim::gmInCalls; sim::gmInBytes += uint64_t(cp.blockCount)*cp.blockLen;
    size_t padded=(cp.blockLen+(pad.leftPadding+pad.rightPadding)*sizeof(T)+31)/32*32;
    for(uint32_t row=0;row<cp.blockCount;++row) {
        size_t dbytes=row*(padded+cp.dstStride*32);
        auto s=reinterpret_cast<uint8_t*>(src.ptr)+row*(cp.blockLen+cp.srcStride);
        sim::checkGlobal(s,cp.blockLen);
        if(pad.isPad) for(size_t j=0;j<padded/sizeof(T);++j)
            dst.SetValue(dbytes/sizeof(T)+j,pad.paddingValue);
        dst.data((dbytes+padded)/sizeof(T)-1);
        std::memcpy(dst.data(dbytes/sizeof(T)+pad.leftPadding),s,cp.blockLen);
    }
}
template<class T> void DataCopyPad(GlobalTensor<T> dst,LocalTensor<T> src,
        const DataCopyExtParams& cp) {
    ++sim::gmOutCalls; sim::gmOutBytes += uint64_t(cp.blockCount)*cp.blockLen;
    size_t padded=(cp.blockLen+31)/32*32;
    for(uint32_t row=0;row<cp.blockCount;++row) {
        size_t sbytes=row*(padded+cp.srcStride*32);
        auto d=reinterpret_cast<uint8_t*>(dst.ptr)+row*(cp.blockLen+cp.dstStride);
        sim::checkGlobal(d,cp.blockLen);
        src.data((sbytes+cp.blockLen)/sizeof(T)-1);
        std::memcpy(d,src.data(sbytes/sizeof(T)),cp.blockLen);
    }
}
template<class T,class F> void Binary(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,uint32_t n,F f) {
    for(uint32_t i=0;i<n;++i) d.SetValue(i, f(a.GetValue(i),b.GetValue(i)));
}
template<class T> void Mul(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,uint32_t n) {
    Binary(d,a,b,n,[](T x,T y){return T(x*y);});
}
template<class T> void Add(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,uint32_t n) {
    Binary(d,a,b,n,[](T x,T y){return T(x+y);});
}
template<class T> void Sub(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,uint32_t n) {
    Binary(d,a,b,n,[](T x,T y){return T(x-y);});
}
template<class T> void Muls(LocalTensor<T>d,LocalTensor<T>a,T scale,uint32_t n) {
    for(uint32_t i=0;i<n;++i) d.SetValue(i,T(a.GetValue(i)*scale));
}
template<class T> void Adds(LocalTensor<T>d,LocalTensor<T>a,T v,uint32_t n) {
    for(uint32_t i=0;i<n;++i) d.SetValue(i,T(a.GetValue(i)+v));
}
template<class T> void Abs(LocalTensor<T>d,LocalTensor<T>a,uint32_t n) {
    for(uint32_t i=0;i<n;++i) d.SetValue(i,T(std::abs(a.GetValue(i))));
}
struct BinaryRepeatParams {
    uint8_t dstBlkStride=1,src0BlkStride=1,src1BlkStride=1;
    uint8_t dstRepStride=8,src0RepStride=8,src1RepStride=8;
};
template<class T> void Mul(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,
        uint64_t mask,uint8_t rows,BinaryRepeatParams p) {
    const size_t nblock=32/sizeof(T);
    for(size_t r=0;r<rows;++r) for(size_t j=0;j<mask;++j) {
        auto idx=[&](size_t rep,size_t stride) {
            return r*rep*nblock+(j/nblock)*stride*nblock+j%nblock; };
        d.SetValue(idx(p.dstRepStride,p.dstBlkStride),
            T(a.GetValue(idx(p.src0RepStride,p.src0BlkStride))*
              b.GetValue(idx(p.src1RepStride,p.src1BlkStride))));
    }
}
template<class T> void Add(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,
        uint64_t mask,uint8_t rows,BinaryRepeatParams p) {
    const size_t nblock=32/sizeof(T);
    for(size_t r=0;r<rows;++r) for(size_t j=0;j<mask;++j) {
        auto idx=[&](size_t rep,size_t stride) {
            return r*rep*nblock+(j/nblock)*stride*nblock+j%nblock; };
        d.SetValue(idx(p.dstRepStride,p.dstBlkStride),
            T(a.GetValue(idx(p.src0RepStride,p.src0BlkStride))+
              b.GetValue(idx(p.src1RepStride,p.src1BlkStride))));
    }
}
template<class T> void Sub(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,
        uint64_t mask,uint8_t rows,BinaryRepeatParams p) {
    const size_t nblock=32/sizeof(T);
    for(size_t r=0;r<rows;++r) for(size_t j=0;j<mask;++j) {
        auto idx=[&](size_t rep,size_t stride) {
            return r*rep*nblock+(j/nblock)*stride*nblock+j%nblock; };
        d.SetValue(idx(p.dstRepStride,p.dstBlkStride),
            T(a.GetValue(idx(p.src0RepStride,p.src0BlkStride))-
              b.GetValue(idx(p.src1RepStride,p.src1BlkStride))));
    }
}
struct CopyRepeatParams { uint16_t dstStride,srcStride,dstRepeatSize,srcRepeatSize; };
template<class T> void Copy(LocalTensor<T>d,LocalTensor<T>a,uint64_t mask,
        uint8_t rows,CopyRepeatParams p) {
    const size_t nb=32/sizeof(T);
    for(size_t r=0;r<rows;++r) for(size_t j=0;j<mask;++j)
        d.SetValue(r*p.dstRepeatSize*nb+j/nb*p.dstStride*nb+j%nb,
            a.GetValue(r*p.srcRepeatSize*nb+j/nb*p.srcStride*nb+j%nb));
}
template<class D,class S> void Cast(LocalTensor<D>d,LocalTensor<S>s,RoundMode mode,uint32_t n) {
    for(uint32_t i=0;i<n;++i) {
        float v=static_cast<float>(s.GetValue(i));
        if(mode==RoundMode::CAST_RINT && sizeof(D)==4)
            v=std::nearbyint(v);
        d.SetValue(i,static_cast<D>(v));
    }
}
template<class T,bool reuse=false> void Sin(LocalTensor<T>d,LocalTensor<T>a,
        LocalTensor<uint8_t>,uint32_t n) {
    for(uint32_t i=0;i<n;++i) d.SetValue(i,std::sin(a.GetValue(i)));
}
template<class T,bool reuse=false> void Cos(LocalTensor<T>d,LocalTensor<T>a,
        LocalTensor<uint8_t>,uint32_t n) {
    for(uint32_t i=0;i<n;++i) d.SetValue(i,std::cos(a.GetValue(i)));
}
}

namespace AscendC {
template<class T, class U> void Axpy(LocalTensor<T> d, LocalTensor<U> s, const U& scale, const int32_t& n) {
    for (int32_t i = 0; i < n; ++i)
        d.SetValue(i, static_cast<T>(std::fma(static_cast<float>(s.GetValue(i)),
            static_cast<float>(scale), static_cast<float>(d.GetValue(i)))));
}
}
