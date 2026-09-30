// SPDX-License-Identifier: MIT
// Register sequence adapted from Waveshare EPD_3in6e.cpp; see THIRD_PARTY_NOTICES.md.
#pragma once
#include <cstddef>
#include <cstdint>

namespace epd36 {
constexpr std::size_t kFrameBytes = 120000; // 400 * 600 / 2, high nibble first
constexpr unsigned kWidth = 400, kHeight = 600;

// Wire format is the panel's sparse native palette: black/white/yellow/red/blue/green.
bool valid_color(std::uint8_t code);

enum class Result : std::uint8_t {
    Ok, PowerUnsafe, NullFrame, WrongSize, InvalidColor, BusFailure, ResetTimeout, InitTimeout,
    PowerOnNoAck, PowerOnTimeout, RefreshNoAck, RefreshTimeout,
    PowerOffNoAck, PowerOffTimeout
};
const char* result_name(Result result);

// Implementations must provide a monotonic modulo-2^32 millisecond clock and
// delay that advances it. hard_off() is unconditional, idempotent and cuts the
// active-low P-MOS rail, releases SPI, then parks output lines LOW. No exceptions.
// write() transmits exactly one byte under CS LOW, with D/C matching is_data.
class IO {
public:
    virtual ~IO() = default;
    virtual void hard_off() = 0;
    virtual bool begin_bus() = 0;
    virtual void rail_on() = 0;
    virtual void reset(bool high) = 0;
    virtual bool write(bool is_data, std::uint8_t byte) = 0;
    virtual bool busy_high() = 0; // LOW = busy, HIGH = ready
    virtual std::uint32_t now_ms() = 0;
    virtual void delay_ms(std::uint32_t ms) = 0;
};

// Engineering limits, not manufacturer-certified maxima; validate on real panels
// at the intended operating temperatures before production release.
struct Timeouts {
    std::uint32_t acknowledge_ms = 1000;
    std::uint32_t reset_ms = 5000;
    std::uint32_t init_ms = 5000;
    std::uint32_t power_ms = 5000;
    std::uint32_t refresh_ms = 60000;
};

class Driver {
public:
    explicit Driver(IO& io, Timeouts limits = {}) : io_(io), limits_(limits) {}
    // Synchronous full-frame update; caller retains immutable storage throughout.
    // Validate transport CRC with portrait::validate_3in6e_frame before calling.
    // Every return, including bad input, leaves the physical rail OFF.
    Result refresh(const std::uint8_t* frame, std::size_t count);
    // Allocation-free bring-up pattern, also validates the native color code.
    Result refresh_solid(std::uint8_t native_color);
private:
    Result run(const std::uint8_t* frame, std::uint8_t solid_byte);
    bool ready(std::uint32_t timeout);
    Result cycle(std::uint32_t timeout, Result no_ack, Result timed_out);
    bool command(std::uint8_t byte) { return io_.write(false, byte); }
    bool data(std::uint8_t byte) { return io_.write(true, byte); }
    IO& io_;
    Timeouts limits_;
};
} // namespace epd36
