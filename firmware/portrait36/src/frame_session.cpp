// SPDX-License-Identifier: MIT
#include "frame_session.h"
#include "portrait_frame.h"
#include <cstring>

namespace epd36 {
const char* session_status_name(SessionStatus status) {
    switch (status) {
#define NAME(x) case SessionStatus::x: return #x
        NAME(Ok); NAME(Busy); NAME(NoMemory); NAME(WrongSize); NAME(BadOffset);
        NAME(NullData); NAME(InvalidColor); NAME(CrcMismatch); NAME(NoFrame);
        NAME(FrameChanged); NAME(Timeout); NAME(DisplayFailed);
#undef NAME
    }
    return "Unknown";
}
bool FrameSession::other_owner(UploadSource source) const {
    return (source != UploadSource::Usb && source != UploadSource::Phone) ||
           (owner_ != UploadSource::None && owner_ != source);
}
void FrameSession::clear() {
    owner_ = UploadSource::None;
    state_ = FrameState::Empty;
    received_ = 0;
    crc_ = 0;
    local_frame_ = false;
}
bool FrameSession::bind_buffer(std::uint8_t* buffer, std::size_t capacity) {
    if (owner_ != UploadSource::None || state_ != FrameState::Empty) return false;
    buffer_ = buffer;
    capacity_ = capacity;
    return buffer != nullptr && capacity >= kFrameBytes;
}
SessionStatus FrameSession::begin(UploadSource source, std::size_t size, std::uint32_t crc, std::uint32_t now) {
    if (other_owner(source) || state_ == FrameState::Receiving) return SessionStatus::Busy;
    if (size != kFrameBytes) return SessionStatus::WrongSize;
    if (!buffer_ || capacity_ < kFrameBytes) return SessionStatus::NoMemory;
    owner_ = source;
    state_ = FrameState::Receiving;
    received_ = 0;
    crc_ = crc;
    local_frame_ = false;
    started_ = last_byte_ = now;
    return SessionStatus::Ok;
}
SessionStatus FrameSession::append(UploadSource source, std::size_t offset, const std::uint8_t* data,
                                    std::size_t count, std::uint32_t now) {
    if (other_owner(source)) return SessionStatus::Busy;
    if (local_frame_) return SessionStatus::Busy;
    if (state_ != FrameState::Receiving) return SessionStatus::NoFrame;
    if (tick(now) == SessionStatus::Timeout) return SessionStatus::Timeout;
    if (offset != received_) return SessionStatus::BadOffset;
    if (!data) return SessionStatus::NullData;
    if (count == 0 || count > kFrameBytes - received_) return SessionStatus::WrongSize;
    std::memcpy(buffer_ + received_, data, count);
    received_ += count;
    last_byte_ = now;
    if (received_ == kFrameBytes) {
        const auto status = portrait::validate_3in6e_frame(buffer_, received_, crc_);
        if (status != portrait::FrameStatus::Valid) {
            clear();
            return status == portrait::FrameStatus::InvalidColor ? SessionStatus::InvalidColor : SessionStatus::CrcMismatch;
        }
        state_ = FrameState::Ready;
    }
    return SessionStatus::Ok;
}
SessionStatus FrameSession::finish(UploadSource source) const {
    if (other_owner(source)) return SessionStatus::Busy;
    return state_ == FrameState::Ready ? SessionStatus::Ok : SessionStatus::NoFrame;
}
SessionStatus FrameSession::show(UploadSource source, std::uint32_t crc, std::uint32_t now) {
    if (other_owner(source)) return SessionStatus::Busy;
    if (tick(now) == SessionStatus::Timeout) return SessionStatus::Timeout;
    if (state_ != FrameState::Ready) return SessionStatus::NoFrame;
    if (crc != crc_) return SessionStatus::CrcMismatch;
    if (portrait::validate_3in6e_frame(buffer_, kFrameBytes, crc_) != portrait::FrameStatus::Valid) {
        clear();
        return SessionStatus::FrameChanged;
    }
    last_byte_ = now;
    display_result_ = sink_.display(buffer_, kFrameBytes);
    return display_result_ == Result::Ok ? SessionStatus::Ok : SessionStatus::DisplayFailed;
}
SessionStatus FrameSession::reset(UploadSource source) {
    if (other_owner(source)) return SessionStatus::Busy;
    clear();
    return SessionStatus::Ok;
}
SessionStatus FrameSession::tick(std::uint32_t now) {
    if ((state_ == FrameState::Receiving &&
         (static_cast<std::uint32_t>(now - last_byte_) >= limits_.idle_ms ||
          static_cast<std::uint32_t>(now - started_) >= limits_.total_ms)) ||
        (state_ == FrameState::Ready && static_cast<std::uint32_t>(now - last_byte_) >= limits_.ready_ms)) {
        clear();
        return SessionStatus::Timeout;
    }
    return SessionStatus::Ok;
}
SessionStatus FrameSession::prepare_local_frame(std::uint32_t now, std::uint8_t*& writable) {
    writable = nullptr;
    if (state_ == FrameState::Receiving) return SessionStatus::Busy;
    if (!buffer_ || capacity_ < kFrameBytes) return SessionStatus::NoMemory;
    clear();
    owner_ = UploadSource::Phone;
    state_ = FrameState::Receiving;
    local_frame_ = true;
    started_ = last_byte_ = now;
    writable = buffer_;
    return SessionStatus::Ok;
}
SessionStatus FrameSession::seal_local_frame(std::uint32_t crc, std::uint32_t now) {
    if (!local_frame_ || owner_ != UploadSource::Phone || state_ != FrameState::Receiving) return SessionStatus::NoFrame;
    const auto status = portrait::validate_3in6e_frame(buffer_, kFrameBytes, crc);
    if (status != portrait::FrameStatus::Valid) {
        clear();
        return status == portrait::FrameStatus::InvalidColor ? SessionStatus::InvalidColor : SessionStatus::CrcMismatch;
    }
    crc_ = crc;
    received_ = kFrameBytes;
    local_frame_ = false;
    state_ = FrameState::Ready;
    last_byte_ = now;
    return SessionStatus::Ok;
}
}  // namespace epd36
