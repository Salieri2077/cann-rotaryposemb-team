cmake_minimum_required(VERSION 3.16)
set(CMAKE_ASC_RUN_MODE "sim" CACHE STRING "ASC execution mode")
set(CMAKE_ASC_ARCHITECTURES "dav-2201" CACHE STRING "NPU architecture")
if(NOT CMAKE_ASC_RUN_MODE STREQUAL "sim")
    message(FATAL_ERROR "This runner is for CAModel: use CMAKE_ASC_RUN_MODE=sim")
endif()
find_package(ASC REQUIRED)
project(rotary_pos_emb_camodel LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(rope_sim_runner sim_runner.asc)
target_include_directories(rope_sim_runner PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(rope_sim_runner PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_compile_options(rope_sim_runner PRIVATE
    $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${CMAKE_ASC_ARCHITECTURES}>
    $<$<COMPILE_LANGUAGE:ASC>:-O2>
    $<$<COMPILE_LANGUAGE:ASC>:-g>
    $<$<COMPILE_LANGUAGE:ASC>:-std=c++17>)
set_target_properties(rope_sim_runner PROPERTIES LINK_FLAGS "-Wl,--disable-new-dtags")
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/kernel.asc" ROPE_KERNEL_SHA)
target_compile_definitions(rope_sim_runner PRIVATE ROPE_KERNEL_SHA="${ROPE_KERNEL_SHA}")
message(STATUS "Kernel SHA256: ${ROPE_KERNEL_SHA}")
