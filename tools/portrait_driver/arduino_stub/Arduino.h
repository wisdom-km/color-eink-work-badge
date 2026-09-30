#pragma once
#include <array>
#include <cstdint>
#include <vector>
#include <cassert>
#include <initializer_list>
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
namespace stub {
struct Pin { int mode=INPUT; int value=LOW; };
struct Event { bool data; std::uint8_t value; bool operator==(const Event& e)const{return data==e.data&&value==e.value;} };
extern std::array<Pin,22> pins;
extern std::vector<Event> events;
extern std::uint32_t clock,trigger;
extern std::uint8_t command;
extern bool force_high,force_low;
extern unsigned end_calls;
}
inline void digitalWrite(int pin,int value){stub::pins.at(pin).value=value;}
inline void pinMode(int pin,int mode){stub::pins.at(pin).mode=mode;}
inline int digitalRead(int pin){
    if(pin!=3)return stub::pins.at(pin).value;
    if(stub::force_high)return HIGH;
    if(stub::force_low)return LOW;
    if(stub::command!=0x04 && stub::command!=0x12 && stub::command!=0x02)return HIGH;
    const auto dt=static_cast<std::uint32_t>(stub::clock-stub::trigger);
    return dt>=2 && dt<7 ? LOW:HIGH;
}
inline std::uint32_t millis(){return stub::clock;}
inline void delay(std::uint32_t n){stub::clock+=n;}
