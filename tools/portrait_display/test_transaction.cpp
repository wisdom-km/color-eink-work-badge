// SPDX-License-Identifier: MIT
// HOST-ONLY behavioral model. Not production storage or a transport protocol.
// A pointer/index swap is a single-thread logical commit, not a durable write,
// ISR synchronization primitive, crash-recovery guarantee, or display update.
#include "portrait_frame.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

using portrait::FrameStatus;
constexpr std::size_t SIZE = portrait::PANEL_3IN6E_FRAME_BYTES;

std::uint32_t crc(const std::vector<std::uint8_t>& data) {
    std::uint32_t value = 0;
    assert(portrait::frame_crc32(data.data(), data.size(), value));
    return value;
}

class InMemoryCommitModel {
public:
    InMemoryCommitModel() : slots_{std::vector<std::uint8_t>(SIZE, 0x11),
                                  std::vector<std::uint8_t>(SIZE, 0x11)} {}

    bool begin(std::size_t expected_size, std::uint32_t expected_crc) {
        if (active_ || expected_size != SIZE) return false;
        expected_crc_ = expected_crc;
        received_ = 0;
        active_ = true;
        return true;
    }
    bool append(std::size_t offset, const std::uint8_t* bytes, std::size_t size) {
        if (!active_ || bytes == nullptr || size == 0 || offset != received_ ||
            size > SIZE - received_) return false;
        std::copy(bytes, bytes + size, slots_[current_ ^ 1U].begin() + static_cast<std::ptrdiff_t>(received_));
        received_ += size;
        return true;
    }
    bool commit() {
        if (!active_ || received_ != SIZE ||
            portrait::validate_3in6e_frame(slots_[current_ ^ 1U].data(), SIZE, expected_crc_) != FrameStatus::Valid) {
            return false;
        }
        current_ ^= 1U;
        active_ = false;
        ++generation_;
        return true;
    }
    void abort() { active_ = false; received_ = 0; }
    const std::vector<std::uint8_t>& visible() const { return slots_[current_]; }
    unsigned generation() const { return generation_; }

private:
    std::array<std::vector<std::uint8_t>, 2> slots_;
    unsigned current_ = 0, generation_ = 0;
    bool active_ = false;
    std::size_t received_ = 0;
    std::uint32_t expected_crc_ = 0;
};

int main() {
    const std::uint8_t known[] = {'1','2','3','4','5','6','7','8','9'};
    std::uint32_t result = 42;
    assert(portrait::frame_crc32(known, sizeof(known), result) && result == 0xCBF43926U);
    assert(portrait::frame_crc32(nullptr, 0, result) && result == 0);
    result = 42;
    assert(!portrait::frame_crc32(nullptr, 1, result) && result == 42);
    assert(portrait::validate_3in6e_frame(nullptr, SIZE, 0) == FrameStatus::NullData);
    std::vector<std::uint8_t> frame(SIZE, 0x11), white = frame;
    assert(portrait::validate_3in6e_frame(frame.data(), SIZE - 1, 0) == FrameStatus::WrongSize);
    assert(portrait::validate_3in6e_frame(frame.data(), SIZE + 1, 0) == FrameStatus::WrongSize);
    const auto legal_code = [](unsigned code) { return code < 16 && ((0x6FU >> code) & 1U) != 0; };
    for (unsigned code = 0; code <= 255; ++code) {
        assert(portrait::is_six_color(static_cast<std::uint8_t>(code)) == legal_code(code));
    }
    for (unsigned byte = 0; byte <= 255; ++byte) {
        std::fill(frame.begin(), frame.end(), static_cast<std::uint8_t>(byte));
        const bool legal = legal_code(byte >> 4) && legal_code(byte & 15);
        assert(portrait::validate_3in6e_frame(frame.data(), SIZE, crc(frame)) ==
               (legal ? FrameStatus::Valid : FrameStatus::InvalidColor));
    }
    const std::uint8_t palette[] = {0, 1, 2, 3, 5, 6};
    for (std::size_t i = 0; i < SIZE; ++i) {
        frame[i] = static_cast<std::uint8_t>((palette[(i * 2) % 6] << 4) | palette[(i * 2 + 1) % 6]);
    }
    const auto expected_crc = crc(frame);
    assert(portrait::validate_3in6e_frame(frame.data(), SIZE, expected_crc) == FrameStatus::Valid);
    assert(portrait::validate_3in6e_frame(frame.data(), SIZE, expected_crc ^ 1U) == FrameStatus::CrcMismatch);
    for (const std::size_t offset : {0U, 1U, 255U, 256U, 4095U, 4096U, 119999U}) {
        for (unsigned bit = 0; bit < 8; ++bit) {
            auto damaged = frame;
            damaged[offset] ^= static_cast<std::uint8_t>(1U << bit);
            assert(portrait::validate_3in6e_frame(damaged.data(), SIZE, expected_crc) != FrameStatus::Valid);
        }
    }

    std::size_t interruption_cases = 0;
    // Every 256-byte packet boundary plus the final short packet: interruptions
    // leave the last committed image unchanged, including after full receipt.
    for (std::size_t stop = 0; stop <= SIZE; stop = std::min(SIZE, stop + 256)) {
        InMemoryCommitModel stage;
        assert(stage.begin(SIZE, expected_crc));
        if (stop != 0) assert(stage.append(0, frame.data(), stop));
        assert(stage.visible() == white && stage.generation() == 0);
        if (stop != SIZE) assert(!stage.commit());
        stage.abort();
        assert(!stage.commit() && stage.visible() == white && stage.generation() == 0);
        ++interruption_cases;
        if (stop == SIZE) break;
    }

    InMemoryCommitModel stage;
    assert(!stage.append(0, frame.data(), 1) && !stage.commit());
    assert(!stage.begin(SIZE - 1, expected_crc));
    assert(stage.begin(SIZE, expected_crc));
    assert(!stage.begin(SIZE, expected_crc));
    assert(!stage.append(1, frame.data(), 1));  // gap/out of order
    assert(!stage.append(0, nullptr, 1));
    assert(!stage.append(0, frame.data(), 0));
    assert(!stage.append(0, frame.data(), SIZE + 1));
    assert(!stage.append(SIZE_MAX, frame.data(), 1));
    std::size_t offset = 0;
    while (offset < SIZE) {
        const auto size = std::min<std::size_t>(256, SIZE - offset);
        assert(stage.append(offset, frame.data() + offset, size));
        assert(!stage.append(offset, frame.data() + offset, size));  // duplicate
        offset += size;
        assert(stage.visible() == white && stage.generation() == 0);
    }
    assert(!stage.append(SIZE, frame.data(), 1));
    assert(stage.commit() && stage.visible() == frame && stage.generation() == 1);
    assert(!stage.commit());
    // A valid-sized but corrupted or illegal pending frame cannot replace it.
    assert(stage.begin(SIZE, expected_crc ^ 1U));
    assert(stage.append(0, frame.data(), SIZE) && !stage.commit());
    assert(stage.visible() == frame && stage.generation() == 1);
    stage.abort();
    auto illegal = frame;
    illegal[SIZE - 1] = 0x44;
    assert(stage.begin(SIZE, crc(illegal)));
    assert(stage.append(0, illegal.data(), SIZE) && !stage.commit());
    assert(stage.visible() == frame && stage.generation() == 1);
    stage.abort();
    // Retry after abort, then a second successful swap back to the first slot.
    assert(stage.begin(SIZE, crc(white)));
    assert(stage.append(0, white.data(), SIZE) && stage.commit());
    assert(stage.visible() == white && stage.generation() == 2);
    std::cout << "{\"passed\":true,\"interruption_boundaries\":" << interruption_cases
              << ",\"all_byte_palette_cases\":256,\"single_bit_corruption_cases\":56,"
              << "\"crc_known_vector\":\"cbf43926\",\"flash_persistence_tested\":false,"
              << "\"physical_display_commit_tested\":false}\n";
}
