// SPDX-License-Identifier: MIT
#include "portrait_frame.h"

#include <cstring>
#include <limits>

namespace portrait {

std::size_t frame_bytes(std::uint32_t width, std::uint32_t height,
                        std::uint8_t bpp) {
    if ((bpp != 1 && bpp != 2 && bpp != 4 && bpp != 8) || width == 0 || height == 0 ||
        width > static_cast<std::uint32_t>(std::numeric_limits<std::int32_t>::max()) ||
        height > static_cast<std::uint32_t>(std::numeric_limits<std::int32_t>::max()) ||
        width > std::numeric_limits<std::size_t>::max() / height) {
        return 0;
    }
    const std::size_t pixels = static_cast<std::size_t>(width) * height;
    const std::size_t per_byte = 8U / bpp;
    // Avoid overflow in both pixels*bpp and pixels+per_byte-1.
    return pixels / per_byte + (pixels % per_byte != 0 ? 1 : 0);
}

PackedFrame::PackedFrame(std::uint8_t* storage, std::size_t capacity,
                         std::uint32_t width, std::uint32_t height,
                         std::uint8_t bpp)
    : storage_(storage), width_(width), height_(height), bpp_(bpp),
      bytes_(frame_bytes(width, height, bpp)),
      valid_(storage != nullptr && bytes_ != 0 && capacity >= bytes_) {}

bool PackedFrame::contains(std::int32_t x, std::int32_t y) const {
    return valid_ && x >= 0 && y >= 0 && static_cast<std::uint32_t>(x) < width_ &&
           static_cast<std::uint32_t>(y) < height_;
}

bool PackedFrame::get(std::int32_t x, std::int32_t y, std::uint8_t& index) const {
    if (!contains(x, y)) return false;
    const std::size_t pixel = static_cast<std::size_t>(y) * width_ + static_cast<std::uint32_t>(x);
    const std::size_t per_byte = 8U / bpp_;
    const unsigned shift = 8 - bpp_ - static_cast<unsigned>(pixel % per_byte) * bpp_;
    const unsigned mask = (1U << bpp_) - 1;
    index = static_cast<std::uint8_t>((static_cast<unsigned>(storage_[pixel / per_byte]) >> shift) & mask);
    return true;
}

bool PackedFrame::set(std::int32_t x, std::int32_t y, std::uint8_t index) {
    if (!contains(x, y) || static_cast<unsigned>(index) >= (1U << bpp_)) return false;
    const std::size_t pixel = static_cast<std::size_t>(y) * width_ + static_cast<std::uint32_t>(x);
    const std::size_t per_byte = 8U / bpp_;
    const unsigned shift = 8 - bpp_ - static_cast<unsigned>(pixel % per_byte) * bpp_;
    const unsigned mask = ((1U << bpp_) - 1) << shift;
    std::uint8_t& byte = storage_[pixel / per_byte];
    byte = static_cast<std::uint8_t>((byte & ~mask) | (static_cast<unsigned>(index) << shift));
    return true;
}

bool PackedFrame::fill(std::uint8_t index) {
    if (!valid_ || static_cast<unsigned>(index) >= (1U << bpp_)) return false;
    unsigned packed = 0;
    for (unsigned shift = 0; shift < 8; shift += bpp_) packed |= unsigned(index) << shift;
    std::memset(storage_, static_cast<int>(packed), bytes_);
    const std::size_t pixels = static_cast<std::size_t>(width_) * height_;
    const unsigned remainder = static_cast<unsigned>(pixels % (8U / bpp_));
    if (remainder != 0) {
        storage_[bytes_ - 1] &= static_cast<std::uint8_t>(0xFFU << (8 - remainder * bpp_));
    }
    return true;
}

bool rotate(const PackedFrame& source, PackedFrame& destination, Rotation rotation) {
    if (!source.valid() || !destination.valid() ||
        source.bits_per_pixel() != destination.bits_per_pixel()) return false;
    const bool quarter = rotation == Rotation::Clockwise90 ||
                         rotation == Rotation::Counterclockwise90;
    if (!quarter && rotation != Rotation::HalfTurn) return false;
    if (destination.width() != (quarter ? source.height() : source.width()) ||
        destination.height() != (quarter ? source.width() : source.height())) return false;

    // Compare offsets instead of end addresses, so even an address addition could
    // not wrap. uintptr_t is available on our embedded and host toolchains.
    const std::uintptr_t a = reinterpret_cast<std::uintptr_t>(source.data());
    const std::uintptr_t b = reinterpret_cast<std::uintptr_t>(destination.data());
    if (a <= b ? b - a < source.size_bytes() : a - b < destination.size_bytes()) return false;

    destination.fill(0);  // Canonical padding; all request checks happened above.
    for (std::uint32_t y = 0; y < source.height(); ++y) {
        for (std::uint32_t x = 0; x < source.width(); ++x) {
            std::uint8_t index = 0;
            source.get(static_cast<std::int32_t>(x), static_cast<std::int32_t>(y), index);
            std::uint32_t dx = source.width() - 1 - x;
            std::uint32_t dy = source.height() - 1 - y;
            if (rotation == Rotation::Clockwise90) { dx = source.height() - 1 - y; dy = x; }
            if (rotation == Rotation::Counterclockwise90) { dx = y; dy = source.width() - 1 - x; }
            destination.set(static_cast<std::int32_t>(dx), static_cast<std::int32_t>(dy), index);
        }
    }
    return true;
}

bool is_six_color(std::uint8_t code) {
    return code == 0 || code == 1 || code == 2 || code == 3 || code == 5 || code == 6;
}

bool frame_crc32(const std::uint8_t* bytes, std::size_t count, std::uint32_t& result) {
    if (bytes == nullptr && count != 0) return false;
    std::uint32_t crc = 0xFFFFFFFFU;
    for (std::size_t i = 0; i < count; ++i) {
        crc ^= bytes[i];
        for (unsigned bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ ((crc & 1U) != 0 ? 0xEDB88320U : 0U);
        }
    }
    result = crc ^ 0xFFFFFFFFU;
    return true;
}

FrameStatus validate_3in6e_frame(const std::uint8_t* bytes, std::size_t count,
                               std::uint32_t expected_crc) {
    if (bytes == nullptr) return FrameStatus::NullData;
    if (count != PANEL_3IN6E_FRAME_BYTES) return FrameStatus::WrongSize;
    for (std::size_t i = 0; i < count; ++i) {
        if (!is_six_color(static_cast<std::uint8_t>(bytes[i] >> 4)) ||
            !is_six_color(static_cast<std::uint8_t>(bytes[i] & 0x0FU))) return FrameStatus::InvalidColor;
    }
    std::uint32_t actual = 0;
    frame_crc32(bytes, count, actual);
    return actual == expected_crc ? FrameStatus::Valid : FrameStatus::CrcMismatch;
}

}  // namespace portrait
