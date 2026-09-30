// SPDX-License-Identifier: MIT
// Host adapter for testing the exact firmware packing/rotation implementation.
#include "portrait_frame.h"

#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    try {
        if (argc == 4 && std::string(argv[1]) == "--validate-3in6e") {
            std::ifstream input(argv[2], std::ios::binary);
            if (!input) throw std::runtime_error("cannot open input");
            std::vector<std::uint8_t> bytes((std::istreambuf_iterator<char>(input)), {});
            std::size_t used = 0;
            const auto crc = std::stoull(argv[3], &used, 16);
            if (used != std::string(argv[3]).size() || crc > 0xFFFFFFFFU) throw std::runtime_error("invalid CRC");
            const auto status = portrait::validate_3in6e_frame(bytes.data(), bytes.size(), static_cast<std::uint32_t>(crc));
            if (status != portrait::FrameStatus::Valid) throw std::runtime_error("native frame rejected: " + std::to_string(unsigned(status)));
            std::cout << "400x600 120000 bytes; legal sparse six-color codes; CRC verified\n";
            return 0;
        }
        if (argc != 7) throw std::runtime_error("usage: frame-cli width height bpp cw|ccw|180 input output");
        const auto number = [](const char* value) -> std::uint32_t {
            std::size_t used = 0;
            const auto n = std::stoull(value, &used);
            if (used != std::string(value).size() || n > 0x7FFFFFFFU) throw std::runtime_error("invalid number");
            return static_cast<std::uint32_t>(n);
        };
        const auto width = number(argv[1]), height = number(argv[2]), depth = number(argv[3]);
        if (depth > 8) throw std::runtime_error("invalid depth");
        const auto bpp = static_cast<std::uint8_t>(depth);
        const auto size = portrait::frame_bytes(width, height, bpp);
        if (!size || size > 64 * 1024 * 1024) throw std::runtime_error("invalid or oversized host frame");
        const std::string direction(argv[4]);
        auto rotation = portrait::Rotation::Clockwise90;
        if (direction == "ccw") rotation = portrait::Rotation::Counterclockwise90;
        else if (direction == "180") rotation = portrait::Rotation::HalfTurn;
        else if (direction != "cw") throw std::runtime_error("invalid rotation");
        std::ifstream input(argv[5], std::ios::binary);
        if (!input) throw std::runtime_error("cannot open input");
        std::vector<std::uint8_t> source((std::istreambuf_iterator<char>(input)), {});
        if (source.size() != size) throw std::runtime_error("input frame size mismatch");
        std::vector<std::uint8_t> target(size, 0);
        portrait::PackedFrame src(source.data(), source.size(), width, height, bpp);
        const bool quarter = rotation != portrait::Rotation::HalfTurn;
        portrait::PackedFrame dst(target.data(), target.size(), quarter ? height : width,
                                  quarter ? width : height, bpp);
        if (!portrait::rotate(src, dst, rotation)) throw std::runtime_error("rotation rejected");
        std::ofstream output(argv[6], std::ios::binary | std::ios::trunc);
        output.write(reinterpret_cast<const char*>(target.data()), static_cast<std::streamsize>(target.size()));
        if (!output) throw std::runtime_error("cannot write output");
        std::cout << dst.width() << "x" << dst.height() << " " << unsigned(bpp)
                  << " bpp " << target.size() << " bytes\n";
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
