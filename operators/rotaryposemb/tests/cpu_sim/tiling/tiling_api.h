#pragma once
#include <vector>
#include <initializer_list>
namespace ge {
struct Shape {
    std::vector<int64_t> dims;
    Shape(std::initializer_list<int64_t> a):dims(a){}
};
}
namespace AscendC {
// Approximate scratch sizes for bounds testing, not the CANN implementation.
inline void GetSinMaxMinTmpSize(const ge::Shape& s,uint32_t,bool,uint32_t& max,uint32_t& min) {
    max=uint32_t((s.dims[0]+63)/64*64*4*8); min=2048;
}
inline void GetCosMaxMinTmpSize(const ge::Shape& s,uint32_t t,bool b,uint32_t& max,uint32_t& min) {
    GetSinMaxMinTmpSize(s,t,b,max,min);
}
}
