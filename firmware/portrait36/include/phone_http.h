// SPDX-License-Identifier: MIT
#pragma once
#include <cstddef>
#include <cstdint>
namespace epd36 {
// Fixed-memory HTTP/1.1 request parser. No allocation proportional to peer
// input.
class PhoneHttpRequest {
public:
  static constexpr std::size_t HeaderLimit = 2048, BodyLimit = 4096;
  enum class State { Headers, Body, Complete, Rejected };
  void reset(std::uint32_t now);
  State feed(std::uint8_t byte, std::uint32_t now);
  State tick(std::uint32_t now);
  State state() const { return state_; }
  unsigned error() const { return error_; }
  const char *method() const { return method_; }
  const char *target() const { return target_; }
  const char *token() const { return token_; }
  const char *content_type() const { return type_; }
  const std::uint8_t *body() const { return body_; }
  std::size_t size() const { return used_; }

private:
  void parse_headers();
  void reject(unsigned status) {
    error_ = status;
    state_ = State::Rejected;
  }
  State state_ = State::Headers;
  unsigned error_ = 0;
  std::size_t header_used_ = 0, used_ = 0, expected_ = 0;
  std::uint32_t started_ = 0;
  char headers_[HeaderLimit + 1] = {}, method_[8] = {}, target_[96] = {},
                              token_[65] = {}, type_[48] = {};
  std::uint8_t body_[BodyLimit] = {};
};
bool phone_token_matches(const char *actual, const char *expected);
bool phone_parse_decimal(const char *text, std::uint32_t &value);
// Strict small JSON object, exact expected fields, no duplicates or unknown
// keys.
bool phone_parse_json(const std::uint8_t *body, std::size_t size,
                      bool need_size, std::uint32_t &frame_size,
                      std::uint32_t &crc);
} // namespace epd36
