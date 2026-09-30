// SPDX-License-Identifier: MIT
#include "portrait_frame.h"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <vector>

using portrait::PackedFrame;
using portrait::Rotation;
std::uint64_t checked_pixels = 0;
std::uint64_t checked_rotations = 0;

// An independent bit-by-bit oracle, deliberately not mirroring byte/shift code.
std::uint8_t oracle(const std::vector<std::uint8_t>& bytes, std::size_t pixel, unsigned bpp) {
    std::uint8_t result = 0;
    for (unsigned bit = 0; bit < bpp; ++bit) {
        const auto pos = pixel * bpp + bit;
        result = static_cast<std::uint8_t>((result << 1) | ((bytes[pos / 8] >> (7 - pos % 8)) & 1));
    }
    return result;
}

void run_case(std::uint32_t width, std::uint32_t height, std::uint8_t bpp, unsigned seed) {
    const auto size = portrait::frame_bytes(width, height, bpp);
    const unsigned colors = 1U << bpp;
    const std::size_t count = static_cast<std::size_t>(width) * height;
    std::vector<std::uint8_t> a(size + 2, 0xCD), b(size + 2, 0xAB), c(size + 2, 0xEF);
    PackedFrame source(a.data() + 1, size, width, height, bpp);
    assert(source.valid() && source.size_bytes() == size && source.fill(0));
    for (std::uint32_t y = 0; y < height; ++y) {
        for (std::uint32_t x = 0; x < width; ++x) {
            const auto index = static_cast<std::uint8_t>((x * 73U + y * 151U + seed) % colors);
            assert(source.set(static_cast<std::int32_t>(x), static_cast<std::int32_t>(y), index));
            std::uint8_t got = 255;
            assert(source.get(static_cast<std::int32_t>(x), static_cast<std::int32_t>(y), got) && got == index);
            ++checked_pixels;
        }
    }
    const std::vector<std::uint8_t> packed(a.begin() + 1, a.end() - 1);
    for (std::size_t n = 0; n < count; ++n) {
        assert(oracle(packed, n, bpp) == (n % width * 73U + n / width * 151U + seed) % colors);
    }
    const auto original = a;
    for (const auto turn : {Rotation::Clockwise90, Rotation::Counterclockwise90, Rotation::HalfTurn}) {
        const bool quarter = turn != Rotation::HalfTurn;
        const auto dw = quarter ? height : width, dh = quarter ? width : height;
        PackedFrame destination(b.data() + 1, size, dw, dh, bpp);
        assert(portrait::rotate(source, destination, turn));
        std::vector<bool> seen(count, false);
        // Inverse-coordinate oracle proves coverage and exactly one source per destination.
        for (std::uint32_t dy = 0; dy < dh; ++dy) {
            for (std::uint32_t dx = 0; dx < dw; ++dx) {
                const auto sx = turn == Rotation::Clockwise90 ? dy :
                                turn == Rotation::Counterclockwise90 ? width - 1 - dy : width - 1 - dx;
                const auto sy = turn == Rotation::Clockwise90 ? height - 1 - dx :
                                turn == Rotation::Counterclockwise90 ? dx : height - 1 - dy;
                const std::size_t pos = static_cast<std::size_t>(sy) * width + sx;
                assert(pos < count && !seen[pos]);
                seen[pos] = true;
                std::uint8_t got = 255;
                assert(destination.get(static_cast<std::int32_t>(dx), static_cast<std::int32_t>(dy), got));
                assert(got == oracle(packed, pos, bpp));
                ++checked_pixels;
            }
        }
        assert(std::all_of(seen.begin(), seen.end(), [](bool hit) { return hit; }));
        PackedFrame restored(c.data() + 1, size, width, height, bpp);
        const auto inverse = turn == Rotation::Clockwise90 ? Rotation::Counterclockwise90 :
                             turn == Rotation::Counterclockwise90 ? Rotation::Clockwise90 : Rotation::HalfTurn;
        assert(portrait::rotate(destination, restored, inverse));
        assert(std::equal(packed.begin(), packed.end(), c.begin() + 1));
        assert(a == original && a.front() == 0xCD && a.back() == 0xCD);
        assert(b.front() == 0xAB && b.back() == 0xAB && c.front() == 0xEF && c.back() == 0xEF);
        ++checked_rotations;
    }
    for (unsigned color = 0; seed == 0 && color < colors; ++color) {
        assert(source.fill(static_cast<std::uint8_t>(color)));
        const std::vector<std::uint8_t> solid(a.begin() + 1, a.end() - 1);
        for (std::size_t n = 0; n < count; ++n) assert(oracle(solid, n, bpp) == color);
        const auto unused = (8 - count * bpp % 8) % 8;
        assert((solid.back() & ((1U << unused) - 1)) == 0);
    }
}

void invalid_cases() {
    assert(portrait::frame_bytes(400, 300, 2) == 30000);
    assert(portrait::frame_bytes(300, 400, 2) == 30000);
    assert(portrait::frame_bytes(480, 720, 4) == 172800);
    assert(portrait::frame_bytes(400, 600, 4) == 120000);
    assert(portrait::frame_bytes(480, 720, 1) == 43200);
    assert(portrait::frame_bytes(3, 3, 1) == 2);
    assert(portrait::frame_bytes(3, 3, 2) == 3);
    assert(portrait::frame_bytes(3, 3, 4) == 5);
    assert(portrait::frame_bytes(0, 1, 2) == 0);
    assert(portrait::frame_bytes(1, 0, 2) == 0);
    for (const auto bpp : {0, 3, 5, 6, 7, 9, 255}) assert(portrait::frame_bytes(5, 5, static_cast<std::uint8_t>(bpp)) == 0);
    assert(portrait::frame_bytes(0xFFFFFFFFU, 2, 2) == 0);
    assert(portrait::frame_bytes(2, 0xFFFFFFFFU, 2) == 0);
    const auto max = static_cast<std::uint32_t>(std::numeric_limits<std::int32_t>::max());
    if (sizeof(std::size_t) == 4) assert(portrait::frame_bytes(max, max, 8) == 0);
    else assert(portrait::frame_bytes(max, max, 8) == static_cast<std::uint64_t>(max) * max);
    std::vector<std::uint8_t> bytes(64, 0xEA), dst(64, 0xDB);
    PackedFrame valid(bytes.data(), bytes.size(), 3, 5, 2);
    const auto before = bytes;
    for (const auto x : {-1, 3, std::numeric_limits<std::int32_t>::min(), std::numeric_limits<std::int32_t>::max()}) {
        std::uint8_t output = 42;
        assert(!valid.set(x, 0, 0) && !valid.get(x, 0, output) && output == 42);
    }
    for (const auto y : {-1, 5, std::numeric_limits<std::int32_t>::min(), std::numeric_limits<std::int32_t>::max()}) {
        std::uint8_t output = 42;
        assert(!valid.set(0, y, 0) && !valid.get(0, y, output) && output == 42);
    }
    for (unsigned color = 4; color < 256; ++color) {
        assert(!valid.set(0, 0, static_cast<std::uint8_t>(color)) && !valid.fill(static_cast<std::uint8_t>(color)));
    }
    assert(bytes == before);
    const PackedFrame invalids[] = {
        {nullptr, 64, 3, 5, 2}, {bytes.data(), 3, 3, 5, 2},
        {bytes.data(), 64, 0, 5, 2}, {bytes.data(), 64, 3, 0, 2},
        {bytes.data(), 64, 3, 5, 3}, {bytes.data(), 64, 0xFFFFFFFFU, 5, 2}
    };
    PackedFrame destination(dst.data(), dst.size(), 5, 3, 2);
    const auto dest_before = dst;
    for (auto bad : invalids) {
        std::uint8_t output = 42;
        assert(!bad.valid() && bad.size_bytes() == 0 && !bad.fill(0));
        assert(!bad.set(0, 0, 0) && !bad.get(0, 0, output) && output == 42);
        assert(!portrait::rotate(bad, destination, Rotation::Clockwise90));
        assert(!portrait::rotate(valid, bad, Rotation::Clockwise90));
    }
    PackedFrame wrong_size(dst.data(), dst.size(), 3, 5, 2);
    PackedFrame wrong_bpp(dst.data(), dst.size(), 5, 3, 4);
    PackedFrame overlap(bytes.data() + 1, bytes.size() - 1, 5, 3, 2);
    PackedFrame overlap_reverse(bytes.data() + 1, bytes.size() - 1, 3, 5, 2);
    PackedFrame overlap_dest(bytes.data(), bytes.size(), 5, 3, 2);
    assert(!portrait::rotate(valid, wrong_size, Rotation::Clockwise90));
    assert(!portrait::rotate(valid, wrong_bpp, Rotation::Clockwise90));
    assert(!portrait::rotate(valid, destination, static_cast<Rotation>(255)));
    assert(!portrait::rotate(valid, overlap, Rotation::Clockwise90));
    assert(!portrait::rotate(overlap_reverse, overlap_dest, Rotation::Clockwise90));
    assert(!portrait::rotate(valid, valid, Rotation::HalfTurn));
    assert(bytes == before && dst == dest_before);
    // Adjacent ranges are allowed; extra supplied capacity must remain untouched.
    PackedFrame adjacent_src(bytes.data(), 64, 3, 5, 2);
    PackedFrame adjacent_dst(bytes.data() + 4, 60, 5, 3, 2);
    assert(portrait::rotate(adjacent_src, adjacent_dst, Rotation::Clockwise90));
    assert(std::equal(bytes.begin() + 8, bytes.end(), before.begin() + 8));
}

int main() {
    invalid_cases();
    for (const auto bpp : {1, 2, 4, 8}) {
        for (std::uint32_t width = 1; width <= 13; ++width) {
            for (std::uint32_t height = 1; height <= 13; ++height) {
                // Every representable index occurs at every logical pixel.
                for (unsigned seed = 0; seed < (1U << bpp); ++seed) run_case(width, height, static_cast<std::uint8_t>(bpp), seed);
            }
        }
    }
    for (unsigned seed = 0; seed < 4; ++seed) run_case(300, 400, 2, seed);
    for (unsigned seed = 0; seed < 16; ++seed) run_case(480, 720, 4, seed);
    for (unsigned seed = 0; seed < 16; ++seed) run_case(400, 600, 4, seed);
    run_case(1, 720, 1, 0);
    run_case(480, 1, 4, 0);
    std::cout << "{\"passed\":true,\"pixel_checks\":" << checked_pixels
              << ",\"rotation_cases\":" << checked_rotations
              << ",\"depths\":[1,2,4,8],\"hardware_validated\":false}\n";
}
