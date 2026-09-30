#pragma once
#include <cstddef>
#define MALLOC_CAP_8BIT 1
namespace fakephone {extern std::size_t free_before,free_after,largest;extern int wifi_mode;}
inline std::size_t heap_caps_get_free_size(int){return fakephone::wifi_mode?fakephone::free_after:fakephone::free_before;}
inline std::size_t heap_caps_get_largest_free_block(int){return fakephone::largest;}
