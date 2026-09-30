// SPDX-License-Identifier: MIT
#pragma once
#include <Arduino.h>
#include <SPI.h>
#include "epd_3in6e.h"
namespace epd36 { namespace c3 {
constexpr int PWR=2, SCK=6, MOSI=7, CS=10, DC=20, RST=21, BUSY=3;
class ArduinoIO final : public epd36::IO {
public:
    void hard_off() override {
        // Set the output latch before output mode, avoiding a LOW pulse at boot.
        digitalWrite(PWR,HIGH); pinMode(PWR,OUTPUT);
        if (active_) { SPI.endTransaction(); SPI.end(); active_=false; }
        for (int pin : {CS,DC,RST,SCK,MOSI}) { digitalWrite(pin,LOW); pinMode(pin,OUTPUT); }
        pinMode(BUSY,INPUT); // no back-power through an enabled internal pull-up
    }
    bool begin_bus() override {
        SPI.begin(SCK,-1,MOSI,-1);
        SPI.beginTransaction(SPISettings(1000000,MSBFIRST,SPI_MODE0));
        active_=true;
        return true; // write-only SPI has no electrical ACK; BUSY is checked separately
    }
    void rail_on() override { digitalWrite(PWR,LOW); digitalWrite(CS,HIGH); }
    void reset(bool high) override { digitalWrite(RST,high ? HIGH : LOW); }
    bool write(bool is_data,std::uint8_t byte) override {
        digitalWrite(DC,is_data ? HIGH : LOW); digitalWrite(CS,LOW);
        SPI.transfer(byte); digitalWrite(CS,HIGH);
        if ((++bytes_ & 1023u)==0) delay(0); // service watchdog during frame streaming
        return true;
    }
    bool busy_high() override { return digitalRead(BUSY)==HIGH; }
    std::uint32_t now_ms() override { return millis(); }
    void delay_ms(std::uint32_t ms) override { delay(ms); }
private:
    bool active_=false;
    std::uint32_t bytes_=0;
};
} }
