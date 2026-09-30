#pragma once
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <string>
#define PROGMEM
#define INPUT 0
#define INPUT_PULLUP 2
#define HIGH 1
#define LOW 0
#define ADC_11db 3
namespace fakephone {
extern std::uint32_t now,bat_adc,usb_adc;
extern bool key_low;
extern std::string serial;
}
inline void pinMode(int,int){}
inline int digitalRead(int pin){return pin==1&&fakephone::key_low?LOW:HIGH;}
inline void analogReadResolution(unsigned){}
inline void analogSetPinAttenuation(int,int){}
inline std::uint32_t analogReadMilliVolts(int pin){return pin==0?fakephone::bat_adc:fakephone::usb_adc;}
inline std::uint32_t millis(){return fakephone::now;}
inline void delay(std::uint32_t ms){fakephone::now+=ms;}
struct FakeSerial {
 void println(const char*s){fakephone::serial+=s;fakephone::serial+='\n';}
 template<typename...T> void printf(const char*f,T...v){char b[512];std::snprintf(b,sizeof(b),f,v...);fakephone::serial+=b;}
};
extern FakeSerial Serial;
