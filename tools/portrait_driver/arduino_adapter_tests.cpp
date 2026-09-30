// SPDX-License-Identifier: MIT
#include "arduino_io.h"
#include <iostream>
namespace stub {
std::array<Pin,22> pins;
std::vector<Event> events;
std::uint32_t clock=0,trigger=0;
std::uint8_t command=0;
bool force_high=false,force_low=false;
unsigned end_calls=0;
}
SPIClass SPI;
using Event=stub::Event;
#include "vendor_oracle.h"
void check_off(){
    assert(stub::pins[2].mode==OUTPUT&&stub::pins[2].value==HIGH);
    for(auto pin:{6,7,10,20,21})assert(stub::pins[pin].mode==OUTPUT&&stub::pins[pin].value==LOW);
    assert(stub::pins[3].mode==INPUT&&!SPI.active&&!SPI.transaction);
}
int main(){
    epd36::c3::ArduinoIO io;io.hard_off();check_off();
    assert(io.begin_bus());io.rail_on();assert(stub::pins[2].value==LOW&&stub::pins[10].value==HIGH);
    io.reset(true);assert(stub::pins[21].value==HIGH);
    io.reset(false);assert(stub::pins[21].value==LOW);
    assert(io.write(false,0xAA));assert(stub::pins[20].value==LOW&&stub::pins[10].value==HIGH);
    assert(io.write(true,0x49));assert(stub::pins[20].value==HIGH&&stub::pins[10].value==HIGH);
    io.hard_off();check_off();const auto ends=stub::end_calls;io.hard_off();check_off();assert(stub::end_calls==ends);
    stub::events.clear();stub::command=0;
    epd36::Driver driver(io);assert(driver.refresh_solid(1)==epd36::Result::Ok);check_off();
    auto expected=oracle_init;expected.push_back({false,0x10});
    expected.insert(expected.end(),120000,Event{true,0x11});
    expected.insert(expected.end(),oracle_turn_on.begin(),oracle_turn_on.end());
    expected.insert(expected.end(),oracle_sleep.begin(),oracle_sleep.end());
    assert(stub::events==expected);
    stub::force_high=true;assert(driver.refresh_solid(1)==epd36::Result::PowerOnNoAck);check_off();stub::force_high=false;
    stub::force_low=true;assert(driver.refresh_solid(1)==epd36::Result::ResetTimeout);check_off();stub::force_low=false;
    assert(driver.refresh_solid(4)==epd36::Result::InvalidColor);check_off();
    std::cout<<"{\"adapter_cases\":5,\"full_spi_bytes_verified\":120061,\"gpio_map_verified\":true,\"rail_cut_before_spi_release\":true}\n";
}
