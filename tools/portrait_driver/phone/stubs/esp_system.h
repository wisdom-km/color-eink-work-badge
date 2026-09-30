#pragma once
#include "WiFi.h"
inline void esp_fill_random(void*p,std::size_t n){assert(fakephone::wifi_mode==WIFI_AP);++fakephone::rng_calls;auto b=static_cast<std::uint8_t*>(p);for(std::size_t i=0;i<n;++i)b[i]=static_cast<std::uint8_t>(i+7*fakephone::rng_calls);}
