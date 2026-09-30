// SPDX-License-Identifier: MIT
#pragma once
#include "frame_session.h"
#include <cstddef>
#include <cstdint>

namespace epd36 {
class UploadSink : public FrameSink {
public:
    virtual ~UploadSink() = default;
    virtual void reply(const char* line) = 0;
};
struct UploadTimeouts {
    std::uint32_t idle_ms = 3000;
    std::uint32_t total_ms = 30000;
    std::uint32_t line_ms = 1000;
};
enum class UploadState : std::uint8_t { Empty, Receiving, Ready, Fault };

// Bounded, allocation-free parser borrowing ONE pending frame. This is not flash
// storage, a previous-frame backup, authentication, or a wireless protocol.
// After BEGIN, receive exactly 120000 raw bytes. Only SHOW <matching CRC> invokes
// hardware, and only after full size/palette/CRC verification. Errors fail closed
// until RESET. Restart means EMPTY; the application must never auto-display.
class UsbReceiver {
public:
    UsbReceiver(UploadSink& sink, FrameSession& session, UploadTimeouts limits = {})
        : sink_(sink), session_(session), limits_(limits) {}
    bool bind_buffer(std::uint8_t* buffer, std::size_t capacity);
    void feed(std::uint8_t byte, std::uint32_t now_ms);
    void tick(std::uint32_t now_ms);
    UploadState state() const { return state_; }
    std::size_t received() const { return session_.owner() == UploadSource::Usb ? session_.received() : 0; }
private:
    void command(std::uint32_t now_ms);
    void fail(const char* reason);
    void reset();
    void reply_crc(const char* prefix);
    UploadSink& sink_;
    FrameSession& session_;
    UploadTimeouts limits_;
    std::size_t line_size_ = 0;
    std::uint32_t expected_crc_ = 0, started_ = 0, last_byte_ = 0;
    UploadState state_ = UploadState::Empty;
    char line_[80] = {};
    bool dropping_line_ = false;
};
}  // namespace epd36
