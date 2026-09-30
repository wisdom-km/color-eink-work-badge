// SPDX-License-Identifier: MIT
#include "usb_receiver.h"
#include "portrait_frame.h"
#include <cstdio>
#include <cstring>

namespace epd36 {
namespace {
bool parse_crc(const char* text, std::uint32_t& value) {
    if (std::strlen(text) != 8) return false;
    value = 0;
    for (unsigned i = 0; i < 8; ++i) {
        const char c = text[i];
        unsigned nibble = 0;
        if (c >= '0' && c <= '9') nibble = static_cast<unsigned>(c - '0');
        else if (c >= 'a' && c <= 'f') nibble = static_cast<unsigned>(c - 'a') + 10U;
        else if (c >= 'A' && c <= 'F') nibble = static_cast<unsigned>(c - 'A') + 10U;
        else return false;
        value = (value << 4) | nibble;
    }
    return true;
}
}

bool UsbReceiver::bind_buffer(std::uint8_t* buffer, std::size_t capacity) {
    return session_.bind_buffer(buffer, capacity);
}
void UsbReceiver::reset() {
    if (session_.reset(UploadSource::Usb) == SessionStatus::Busy) {
        sink_.reply("ERR BUSY"); return;
    }
    state_ = UploadState::Empty;
    line_size_ = 0;
    expected_crc_ = 0;
    dropping_line_ = false;
    sink_.reply("RESET");
}
void UsbReceiver::fail(const char* reason) {
    session_.reset(UploadSource::Usb); // cannot reset a Phone-owned session
    state_ = UploadState::Fault;
    line_size_ = 0;
    expected_crc_ = 0;
    sink_.reply(reason);
}
void UsbReceiver::reply_crc(const char* prefix) {
    char reply[64];
    std::snprintf(reply, sizeof(reply), "%s %08lX", prefix, static_cast<unsigned long>(expected_crc_));
    sink_.reply(reply);
}
void UsbReceiver::tick(std::uint32_t now) {
    // A physical pairing action may replace a staged USB image. Do not retain
    // stale READY/CRC metadata after that explicit local takeover or expiration.
    if (state_ == UploadState::Ready &&
        (session_.owner() != UploadSource::Usb || session_.state() != FrameState::Ready)) {
        state_ = UploadState::Empty;
        expected_crc_ = 0;
    }
    if (state_ == UploadState::Ready && session_.owner() == UploadSource::Usb &&
        session_.tick(now) == SessionStatus::Timeout) { fail("ERR FRAME_EXPIRED RESET_REQUIRED"); return; }
    if (state_ == UploadState::Receiving &&
        (static_cast<std::uint32_t>(now - last_byte_) >= limits_.idle_ms ||
         static_cast<std::uint32_t>(now - started_) >= limits_.total_ms)) {
        fail("ERR RECEIVE_TIMEOUT RESET_REQUIRED");
    } else if (line_size_ != 0 && static_cast<std::uint32_t>(now - last_byte_) >= limits_.line_ms) {
        fail("ERR LINE_TIMEOUT RESET_REQUIRED");
        dropping_line_ = false;
    }
}
void UsbReceiver::feed(std::uint8_t byte, std::uint32_t now) {
    tick(now);
    last_byte_ = now;
    if (state_ == UploadState::Receiving) {
        const auto status = session_.append(UploadSource::Usb, session_.received(), &byte, 1, now);
        if (status == SessionStatus::Ok) {
            if (session_.state() == FrameState::Ready) {
                state_ = UploadState::Ready;
                reply_crc("FRAME");
            }
        } else if (status == SessionStatus::InvalidColor) fail("ERR INVALID_COLOR RESET_REQUIRED");
        else if (status == SessionStatus::CrcMismatch) fail("ERR CRC RESET_REQUIRED");
        else fail("ERR RECEIVE RESET_REQUIRED");
        return;
    }
    if (byte == '\r') return;
    if (byte == '\n') {
        if (dropping_line_) { dropping_line_ = false; line_size_ = 0; return; }
        if (line_size_ == 0) return;
        line_[line_size_] = '\0';
        command(now);
        line_size_ = 0;
        return;
    }
    if (dropping_line_) return;
    if (byte < 32 || byte > 126 || line_size_ >= sizeof(line_) - 1) {
        fail("ERR COMMAND_FORMAT RESET_REQUIRED");
        dropping_line_ = true;  // discard the rest of this malformed line
        return;
    }
    line_[line_size_++] = static_cast<char>(byte);
}
void UsbReceiver::command(std::uint32_t now) {
    if (session_.owner() == UploadSource::Phone) { sink_.reply("ERR BUSY"); return; }
    if (std::strcmp(line_, "RESET") == 0) { reset(); return; }
    if (state_ == UploadState::Fault) { sink_.reply("ERR RESET_REQUIRED"); return; }
    if (std::strcmp(line_, "HELLO") == 0) {
        if (state_ == UploadState::Ready) reply_crc("P36V1 READY");
        else sink_.reply("P36V1 EMPTY");
        return;
    }
    if (std::strncmp(line_, "BEGIN ", 6) == 0) {
        // Fixed literal length avoids signs, integer overflow, extra fields and
        // ambiguous dimensions. A frame is ALWAYS native 400x600, 4-bit.
        if (std::strncmp(line_ + 6, "120000 ", 7) != 0 || !parse_crc(line_ + 13, expected_crc_)) {
            fail("ERR HEADER RESET_REQUIRED"); return;
        }
        const auto status = session_.begin(UploadSource::Usb, kFrameBytes, expected_crc_, now);
        if (status == SessionStatus::Busy) { sink_.reply("ERR BUSY"); return; }
        if (status != SessionStatus::Ok) { fail("ERR NO_MEMORY RESET_REQUIRED"); return; }
        state_ = UploadState::Receiving;
        started_ = last_byte_ = now;
        sink_.reply("READY 120000");
        return;
    }
    if (std::strncmp(line_, "SHOW ", 5) == 0) {
        std::uint32_t crc = 0;
        if (state_ != UploadState::Ready || !parse_crc(line_ + 5, crc) || crc != expected_crc_) {
            fail("ERR NO_MATCHING_FRAME RESET_REQUIRED"); return;
        }
        // Revalidate immediately before invoking hardware, including if SHOW is
        // a retry after a previous driver failure. The buffer stays immutable.
        reply_crc("DISPLAYING");
        const auto status = session_.show(UploadSource::Usb, expected_crc_, now);
        if (status == SessionStatus::Ok) reply_crc("DISPLAY OK");
        else if (status == SessionStatus::Busy) sink_.reply("ERR BUSY");
        else if (status != SessionStatus::DisplayFailed) fail("ERR FRAME_CHANGED RESET_REQUIRED");
        else {
            const auto result = session_.last_display_result();
            char reply[96];
            std::snprintf(reply, sizeof(reply), "ERR DISPLAY %s %s", result_name(result),
                          result == Result::PowerUnsafe ? "NOT_STARTED" : "PANEL_STATE_UNKNOWN");
            sink_.reply(reply);
        }
        return;
    }
    fail("ERR COMMAND RESET_REQUIRED");
}
}  // namespace epd36
