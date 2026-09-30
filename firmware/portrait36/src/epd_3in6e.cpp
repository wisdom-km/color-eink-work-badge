// SPDX-License-Identifier: MIT
// Waveshare register sequence (MIT); full notice in ../THIRD_PARTY_NOTICES.md.
#include "epd_3in6e.h"

namespace epd36 {
namespace {
struct OffGuard { IO& io; ~OffGuard() { io.hard_off(); } };
struct Register { std::uint8_t command, count, bytes[6]; };
// Exact order/data from the pinned official 3.6inch E ESP32 driver Init().
constexpr Register kInit[] = {
    {0xAA,6,{0x49,0x55,0x20,0x08,0x09,0x18}},
    {0x01,1,{0x3F}}, {0x00,2,{0x5F,0x69}},
    {0x05,4,{0x40,0x1F,0x1F,0x2C}},
    {0x08,4,{0x6F,0x1F,0x1F,0x22}},
    {0x06,4,{0x6F,0x1F,0x17,0x17}},
    {0x03,4,{0x00,0x54,0x00,0x44}},
    {0x60,2,{0x02,0x00}}, {0x30,1,{0x08}}, {0x50,1,{0x3F}},
    {0x61,4,{0x01,0x90,0x02,0x58}}, {0xE3,1,{0x2F}}, {0x84,1,{0x01}}
};
}
bool valid_color(std::uint8_t code) {
    return code <= 3 || code == 5 || code == 6;
}
const char* result_name(Result r) {
    switch (r) {
#define NAME(x) case Result::x: return #x
        NAME(Ok); NAME(PowerUnsafe); NAME(NullFrame); NAME(WrongSize); NAME(InvalidColor);
        NAME(BusFailure); NAME(ResetTimeout); NAME(InitTimeout);
        NAME(PowerOnNoAck); NAME(PowerOnTimeout); NAME(RefreshNoAck);
        NAME(RefreshTimeout); NAME(PowerOffNoAck); NAME(PowerOffTimeout);
#undef NAME
    }
    return "Unknown";
}

// Reset/initialization may have finished before sampling; only wait for ready.
bool Driver::ready(std::uint32_t timeout) {
    const auto start = io_.now_ms();
    while (!io_.busy_high()) {
        if (static_cast<std::uint32_t>(io_.now_ms() - start) >= timeout) return false;
        io_.delay_ms(1);
    }
    io_.delay_ms(100); // vendor post-BUSY settle
    return true;
}

// Commands 04/12/02 must actually be acknowledged LOW and then return HIGH.
// This deliberately rejects a detached/stuck-HIGH BUSY line; vendor only waits
// while LOW and would otherwise report instant success with no display attached.
Result Driver::cycle(std::uint32_t timeout, Result no_ack, Result timed_out) {
    const auto start = io_.now_ms();
    while (io_.busy_high()) {
        if (static_cast<std::uint32_t>(io_.now_ms()-start) >= limits_.acknowledge_ms)
            return no_ack;
        io_.delay_ms(1);
    }
    const auto busy_start = io_.now_ms();
    while (!io_.busy_high()) {
        if (static_cast<std::uint32_t>(io_.now_ms()-busy_start) >= timeout)
            return timed_out;
        io_.delay_ms(1);
    }
    io_.delay_ms(100);
    return Result::Ok;
}

Result Driver::refresh(const std::uint8_t* frame, std::size_t count) {
    io_.hard_off();
    OffGuard off{io_};
    if (!frame) return Result::NullFrame;
    if (count != kFrameBytes) return Result::WrongSize;
    for (std::size_t i=0; i<count; ++i)
        if (!valid_color(frame[i] >> 4) || !valid_color(frame[i] & 15))
            return Result::InvalidColor;
    return run(frame, 0);
}
Result Driver::refresh_solid(std::uint8_t code) {
    io_.hard_off();
    OffGuard off{io_};
    if (!valid_color(code)) return Result::InvalidColor;
    return run(nullptr, static_cast<std::uint8_t>((code << 4) | code));
}
Result Driver::run(const std::uint8_t* frame, std::uint8_t solid) {
    if (!io_.begin_bus()) return Result::BusFailure;
    io_.rail_on();
    io_.delay_ms(20); // switched supply stabilization before vendor reset
    io_.reset(true); io_.delay_ms(200);
    io_.reset(false); io_.delay_ms(20);
    io_.reset(true); io_.delay_ms(200);
    if (!ready(limits_.reset_ms)) return Result::ResetTimeout;
    io_.delay_ms(30);
    for (const auto& r : kInit) {
        if (!command(r.command)) return Result::BusFailure;
        for (unsigned i=0; i<r.count; ++i)
            if (!data(r.bytes[i])) return Result::BusFailure;
    }
    if (!ready(limits_.init_ms)) return Result::InitTimeout;
    if (!command(0x10)) return Result::BusFailure;
    for (std::size_t i=0; i<kFrameBytes; ++i)
        if (!data(frame ? frame[i] : solid)) return Result::BusFailure;

    // Official TurnOnDisplay(): power on, second booster setting, refresh, off.
    if (!command(0x04)) return Result::BusFailure;
    auto result = cycle(limits_.power_ms, Result::PowerOnNoAck, Result::PowerOnTimeout);
    if (result != Result::Ok) return result;
    io_.delay_ms(200);
    if (!command(0x06)) return Result::BusFailure;
    const std::uint8_t booster[] = {0x6F,0x1F,0x16,0x29};
    for (auto byte : booster) if (!data(byte)) return Result::BusFailure;
    io_.delay_ms(200);
    if (!command(0x12) || !data(0x00)) return Result::BusFailure;
    result = cycle(limits_.refresh_ms, Result::RefreshNoAck, Result::RefreshTimeout);
    if (result != Result::Ok) return result;
    if (!command(0x02) || !data(0x00)) return Result::BusFailure;
    result = cycle(limits_.power_ms, Result::PowerOffNoAck, Result::PowerOffTimeout);
    if (result != Result::Ok) return result;
    if (!command(0x07) || !data(0xA5)) return Result::BusFailure;
    // No commands after a failed/timed-out BUSY stage; OffGuard cuts rail directly.
    return Result::Ok;
}
} // namespace epd36
