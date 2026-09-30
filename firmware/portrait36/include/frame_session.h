// SPDX-License-Identifier: MIT
#pragma once
#include "epd_3in6e.h"
#include <cstddef>
#include <cstdint>

namespace epd36 {
enum class UploadSource : std::uint8_t { None, Usb, Phone };
enum class FrameState : std::uint8_t { Empty, Receiving, Ready };
enum class SessionStatus : std::uint8_t {
    Ok, Busy, NoMemory, WrongSize, BadOffset, NullData, InvalidColor,
    CrcMismatch, NoFrame, FrameChanged, Timeout, DisplayFailed
};
const char* session_status_name(SessionStatus status);
class FrameSink {
public:
    virtual ~FrameSink() = default;
    virtual Result display(const std::uint8_t* frame, std::size_t size) = 0;
};
struct FrameTimeouts {
    std::uint32_t idle_ms = 3000;
    std::uint32_t total_ms = 30000;
    std::uint32_t ready_ms = 120000;
};

// Single main-loop owner only; not thread safe. USB and authenticated local HTTP
// share ONE borrowed buffer. Never call from two tasks or interrupt handlers.
// An active owner's frame cannot be changed, reset or displayed by the other
// source. No copy of the previous frame and no flash persistence are provided.
class FrameSession {
public:
    explicit FrameSession(FrameSink& sink, FrameTimeouts limits = {}) : sink_(sink), limits_(limits) {}
    bool bind_buffer(std::uint8_t* buffer, std::size_t capacity);
    SessionStatus begin(UploadSource source, std::size_t size, std::uint32_t crc, std::uint32_t now);
    SessionStatus append(UploadSource source, std::size_t offset, const std::uint8_t* data,
                         std::size_t count, std::uint32_t now);
    SessionStatus finish(UploadSource source) const;
    SessionStatus show(UploadSource source, std::uint32_t crc, std::uint32_t now);
    SessionStatus reset(UploadSource source);
    SessionStatus tick(std::uint32_t now);
    // Physical-local action only, e.g. the user long-pressing UPDATE to replace
    // the picture with temporary pairing credentials. Never expose via HTTP.
    // Refuses an in-progress upload. May replace Ready, even owned by USB.
    SessionStatus prepare_local_frame(std::uint32_t now, std::uint8_t*& writable);
    SessionStatus seal_local_frame(std::uint32_t crc, std::uint32_t now);
    UploadSource owner() const { return owner_; }
    FrameState state() const { return state_; }
    std::size_t received() const { return received_; }
    std::uint32_t crc() const { return crc_; }
    Result last_display_result() const { return display_result_; }
private:
    void clear();
    bool other_owner(UploadSource source) const;
    FrameSink& sink_;
    FrameTimeouts limits_;
    std::uint8_t* buffer_ = nullptr;
    std::size_t capacity_ = 0, received_ = 0;
    UploadSource owner_ = UploadSource::None;
    FrameState state_ = FrameState::Empty;
    std::uint32_t crc_ = 0, started_ = 0, last_byte_ = 0;
    Result display_result_ = Result::Ok;
    bool local_frame_ = false;
};
}  // namespace epd36
