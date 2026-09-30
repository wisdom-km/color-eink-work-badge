// SPDX-License-Identifier: MIT
#include "phone_setup_render.h"
#include "epd_3in6e.h"
#include <cstring>
namespace epd36 {
namespace {
// Rows, five low bits per row. Deliberately simple self-contained ASCII labels.
const std::uint8_t digits[10][7] = {
    {14, 17, 19, 21, 25, 17, 14}, {4, 12, 4, 4, 4, 4, 14},
    {14, 17, 1, 2, 4, 8, 31},     {30, 1, 1, 14, 1, 1, 30},
    {2, 6, 10, 18, 31, 2, 2},     {31, 16, 16, 30, 1, 1, 30},
    {14, 16, 16, 30, 17, 17, 14}, {31, 1, 2, 4, 8, 8, 8},
    {14, 17, 17, 14, 17, 17, 14}, {14, 17, 17, 15, 1, 1, 14}};
const std::uint8_t letters[26][7] = {
    {14, 17, 17, 31, 17, 17, 17}, {30, 17, 17, 30, 17, 17, 30},
    {14, 17, 16, 16, 16, 17, 14}, {30, 17, 17, 17, 17, 17, 30},
    {31, 16, 16, 30, 16, 16, 31}, {31, 16, 16, 30, 16, 16, 16},
    {14, 17, 16, 23, 17, 17, 15}, {17, 17, 17, 31, 17, 17, 17},
    {14, 4, 4, 4, 4, 4, 14},      {7, 2, 2, 2, 18, 18, 12},
    {17, 18, 20, 24, 20, 18, 17}, {16, 16, 16, 16, 16, 16, 31},
    {17, 27, 21, 21, 17, 17, 17}, {17, 25, 21, 19, 17, 17, 17},
    {14, 17, 17, 17, 17, 17, 14}, {30, 17, 17, 30, 16, 16, 16},
    {14, 17, 17, 17, 21, 18, 13}, {30, 17, 17, 30, 20, 18, 17},
    {15, 16, 16, 14, 1, 1, 30},   {31, 4, 4, 4, 4, 4, 4},
    {17, 17, 17, 17, 17, 17, 14}, {17, 17, 17, 17, 17, 10, 4},
    {17, 17, 17, 21, 21, 21, 10}, {17, 17, 10, 4, 10, 17, 17},
    {17, 17, 10, 4, 4, 4, 4},     {31, 1, 2, 4, 8, 16, 31}};
std::uint8_t row(char c, unsigned y) {
  if (c >= 'a' && c <= 'z')
    c = static_cast<char>(c - 'a' + 'A');
  if (c >= 'A' && c <= 'Z')
    return letters[c - 'A'][y];
  if (c >= '0' && c <= '9')
    return digits[c - '0'][y];
  if (c == ':')
    return y == 2 || y == 5 ? 4 : 0;
  if (c == '.')
    return y == 6 ? 4 : 0;
  if (c == '-')
    return y == 3 ? 14 : 0;
  if (c == '/')
    return static_cast<std::uint8_t>(1u << (y < 2   ? 0
                                            : y < 3 ? 1
                                            : y < 5 ? 2
                                            : y < 6 ? 3
                                                    : 4));
  return 0;
}
void pixel(std::uint8_t *f, unsigned x, unsigned y) {
  if (x >= kWidth || y >= kHeight)
    return;
  const auto i = (static_cast<std::size_t>(y) * kWidth + x) / 2;
  if (x & 1)
    f[i] &= 0xF0;
  else
    f[i] &= 0x0F;
}
void text(std::uint8_t *f, unsigned x, unsigned y, const char *s,
          unsigned scale) {
  for (; *s; ++s, x += 6 * scale) {
    for (unsigned r = 0; r < 7; ++r)
      for (unsigned c = 0; c < 5; ++c)
        if (row(*s, r) & (1u << (4 - c)))
          for (unsigned dy = 0; dy < scale; ++dy)
            for (unsigned dx = 0; dx < scale; ++dx)
              pixel(f, x + c * scale + dx, y + r * scale + dy);
  }
}
bool safe_text(const char *s, std::size_t max) {
  if (!s || !std::strlen(s) || std::strlen(s) > max)
    return false;
  for (; *s; ++s)
    if (!((*s >= 'A' && *s <= 'Z') || (*s >= '0' && *s <= '9') || *s == '-'))
      return false;
  return true;
}
} // namespace
bool phone_render_setup(std::uint8_t *f, std::size_t n, const char *ssid,
                        const char *pass, const char *token) {
  if (!f || n != kFrameBytes || !safe_text(ssid, 20) || !safe_text(pass, 16) ||
      !token || std::strlen(token) != 32)
    return false;
  for (unsigned i = 0; i < 32; ++i)
    if (!((token[i] >= '0' && token[i] <= '9') ||
          (token[i] >= 'A' && token[i] <= 'F')))
      return false;
  std::memset(f, 0x11, n);
  text(f, 20, 24, "P36 PHONE SETUP", 3);
  text(f, 20, 66, "TEMPORARY - 10 MINUTES", 2);
  text(f, 20, 108, "WIFI NAME", 2);
  text(f, 20, 134, ssid, 3);
  text(f, 20, 182, "PASSWORD", 2);
  text(f, 20, 210, pass, 3);
  text(f, 20, 266, "OPEN IN YOUR BROWSER", 2);
  text(f, 20, 294, "HTTP://192.168.4.1", 2);
  text(f, 20, 342, "UPLOAD TOKEN - JOIN BOTH LINES", 1);
  char half[17] = {};
  std::memcpy(half, token, 16);
  text(f, 20, 366, half, 3);
  std::memcpy(half, token + 16, 16);
  text(f, 20, 402, half, 3);
  text(f, 20, 456, "SELECT A PICTURE THEN SHOW", 2);
  text(f, 20, 498, "THIS REPLACED THE OLD IMAGE", 2);
  text(f, 20, 532, "EXPIRED: HOLD UPDATE TO RESTART", 2);
  text(f, 20, 566, "NO CLOUD - NO HOME WIFI", 2);
  return true;
}
} // namespace epd36
