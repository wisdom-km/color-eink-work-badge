// SPDX-License-Identifier: MIT
#pragma once

#include <cstddef>
#include <cstdint>

// Hardware-independent indexed pixels. No panel commands, allocation or transport.
// Rows follow each other without byte padding. The first pixel occupies the most
// significant bits. Palette indices are NOT any particular controller's encoding.
namespace portrait {

// Returns zero for unsupported bpp, zero dimensions, or arithmetic overflow.
// Supported depths are 1, 2, 4 and 8. Dimensions must fit signed pixel coordinates.
std::size_t frame_bytes(std::uint32_t width, std::uint32_t height,
                        std::uint8_t bits_per_pixel);

class PackedFrame {
public:
    // Borrows storage; caller keeps it alive. Extra capacity is never touched.
    PackedFrame(std::uint8_t* storage, std::size_t capacity,
                std::uint32_t width, std::uint32_t height,
                std::uint8_t bits_per_pixel);

    bool valid() const { return valid_; }
    std::uint32_t width() const { return width_; }
    std::uint32_t height() const { return height_; }
    std::uint8_t bits_per_pixel() const { return bpp_; }
    std::size_t size_bytes() const { return valid_ ? bytes_ : 0; }
    const std::uint8_t* data() const { return storage_; }

    // Failure leaves the output/storage unchanged. Negative/out-of-range pixels
    // and indices that do not fit the selected depth are rejected, never wrapped.
    bool get(std::int32_t x, std::int32_t y, std::uint8_t& index) const;
    bool set(std::int32_t x, std::int32_t y, std::uint8_t index);
    // Unused low bits in the final byte are canonicalized to zero.
    bool fill(std::uint8_t index);

private:
    bool contains(std::int32_t x, std::int32_t y) const;
    std::uint8_t* storage_;
    std::uint32_t width_;
    std::uint32_t height_;
    std::uint8_t bpp_;
    std::size_t bytes_;
    bool valid_;
};

enum class Rotation : std::uint8_t { Clockwise90, HalfTurn, Counterclockwise90 };

// Requires valid, disjoint frames with identical depths and matching dimensions.
// Invalid requests leave destination untouched. No allocation; never rotates in
// place. Clockwise: destination(H - 1 - y, x) = source(x, y).
// Counterclockwise: destination(y, W - 1 - x) = source(x, y).
// Half turn: destination(W - 1 - x, H - 1 - y) = source(x, y).
bool rotate(const PackedFrame& source, PackedFrame& destination, Rotation rotation);

// Waveshare 3.6inch e-Paper (E), official EPD_3in6e.h color codes.
// These nibble values are sparse: 4 and 7..15 must never reach the panel.
enum class SixColor : std::uint8_t {
    Black = 0x0, White = 0x1, Yellow = 0x2, Red = 0x3, Blue = 0x5, Green = 0x6
};
constexpr std::uint32_t PANEL_3IN6E_WIDTH = 400;
constexpr std::uint32_t PANEL_3IN6E_HEIGHT = 600;
constexpr std::size_t PANEL_3IN6E_FRAME_BYTES = 120000;
bool is_six_color(std::uint8_t code);

// CRC-32/ISO-HDLC (IEEE): polynomial 0xEDB88320, init/final XOR 0xFFFFFFFF.
// Empty data has CRC zero. A null nonempty input fails without changing result.
// CRC detects accidental corruption; it does not authenticate a sender.
bool frame_crc32(const std::uint8_t* bytes, std::size_t count, std::uint32_t& result);

enum class FrameStatus : std::uint8_t { Valid, NullData, WrongSize, InvalidColor, CrcMismatch };
// Exact full 400x600 native portrait frame, high nibble first, no row padding.
// Does not write data, access hardware, store credentials, or persist anything.
FrameStatus validate_3in6e_frame(const std::uint8_t* bytes, std::size_t count,
                               std::uint32_t expected_crc);

}  // namespace portrait
