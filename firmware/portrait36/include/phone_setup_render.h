// SPDX-License-Identifier: MIT
#pragma once
#include <cstddef>
#include <cstdint>
namespace epd36 {
// Own compact 5x7 bitmap glyphs, black on white, no allocation or second frame.
bool phone_render_setup(std::uint8_t *frame, std::size_t count,
                        const char *ssid, const char *password,
                        const char *token);
} // namespace epd36
