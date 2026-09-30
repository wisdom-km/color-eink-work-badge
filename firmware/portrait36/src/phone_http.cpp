// SPDX-License-Identifier: MIT
#include "phone_http.h"
#include <cstring>
namespace epd36 {
namespace {
char lower(char c) {
  return c >= 'A' && c <= 'Z' ? static_cast<char>(c - 'A' + 'a') : c;
}
bool equal_ci(const char *a, const char *b) {
  while (*a && *b) {
    if (lower(*a++) != lower(*b++))
      return false;
  }
  return *a == *b;
}
bool copy(char *to, std::size_t cap, const char *from) {
  const auto n = std::strlen(from);
  if (n >= cap)
    return false;
  std::memcpy(to, from, n + 1);
  return true;
}
bool type_is(const char *type, const char *expected) {
  while (*expected) {
    if (lower(*type++) != *expected++)
      return false;
  }
  return *type == '\0' || *type == ';';
}
} // namespace
void PhoneHttpRequest::reset(std::uint32_t now) {
  state_ = State::Headers;
  error_ = 0;
  header_used_ = used_ = expected_ = 0;
  started_ = now;
  method_[0] = target_[0] = token_[0] = type_[0] = 0;
}
PhoneHttpRequest::State PhoneHttpRequest::tick(std::uint32_t now) {
  if (state_ != State::Complete && state_ != State::Rejected &&
      static_cast<std::uint32_t>(now - started_) >= 5000)
    reject(408);
  return state_;
}
PhoneHttpRequest::State PhoneHttpRequest::feed(std::uint8_t b,
                                               std::uint32_t now) {
  if (tick(now) == State::Rejected || state_ == State::Complete)
    return state_;
  if (state_ == State::Headers) {
    if (!b) {
      reject(400);
      return state_;
    }
    if (header_used_ >= HeaderLimit) {
      reject(431);
      return state_;
    }
    headers_[header_used_++] = static_cast<char>(b);
    headers_[header_used_] = 0;
    if (header_used_ >= 4 &&
        std::memcmp(headers_ + header_used_ - 4, "\r\n\r\n", 4) == 0)
      parse_headers();
  } else {
    if (used_ >= expected_ || used_ >= BodyLimit) {
      reject(413);
      return state_;
    }
    body_[used_++] = b;
    if (used_ == expected_)
      state_ = State::Complete;
  }
  return state_;
}
bool phone_parse_decimal(const char *s, std::uint32_t &v) {
  if (!s || !*s)
    return false;
  std::uint32_t n = 0;
  for (; *s; ++s) {
    if (*s < '0' || *s > '9')
      return false;
    unsigned d = *s - '0';
    if (n > (UINT32_MAX - d) / 10)
      return false;
    n = n * 10 + d;
  }
  v = n;
  return true;
}
void PhoneHttpRequest::parse_headers() {
  char *line = headers_;
  char *end = std::strstr(line, "\r\n");
  if (!end) {
    reject(400);
    return;
  }
  *end = 0;
  char *a = std::strchr(line, ' ');
  if (!a) {
    reject(400);
    return;
  }
  *a++ = 0;
  char *b = std::strchr(a, ' ');
  if (!b) {
    reject(400);
    return;
  }
  *b++ = 0;
  if (std::strcmp(b, "HTTP/1.1") || !copy(method_, sizeof(method_), line) ||
      !copy(target_, sizeof(target_), a) || target_[0] != '/') {
    reject(400);
    return;
  }
  if (std::strcmp(method_, "GET") && std::strcmp(method_, "POST")) {
    reject(405);
    return;
  }
  bool length = false, host = false, token = false, type = false,
       origin = false;
  line = end + 2;
  while (*line) {
    end = std::strstr(line, "\r\n");
    if (!end) {
      reject(400);
      return;
    }
    *end = 0;
    if (!*line)
      break;
    if (*line == ' ' || *line == '\t') {
      reject(400);
      return;
    }
    char *value = std::strchr(line, ':');
    if (!value) {
      reject(400);
      return;
    }
    *value++ = 0;
    while (*value == ' ' || *value == '\t')
      ++value;
    char *tail = value + std::strlen(value);
    while (tail > value && (tail[-1] == ' ' || tail[-1] == '\t'))
      *--tail = 0;
    if (equal_ci(line, "Transfer-Encoding")) {
      reject(400);
      return;
    }
    if (equal_ci(line, "Content-Length")) {
      std::uint32_t n = 0;
      if (length || !phone_parse_decimal(value, n)) {
        reject(400);
        return;
      }
      length = true;
      expected_ = n;
      if (n > BodyLimit) {
        reject(413);
        return;
      }
    } else if (equal_ci(line, "Host")) {
      if (host || (std::strcmp(value, "192.168.4.1") &&
                   std::strcmp(value, "192.168.4.1:80"))) {
        reject(400);
        return;
      }
      host = true;
    } else if (equal_ci(line, "Origin")) {
      if (origin || (std::strcmp(value, "http://192.168.4.1") &&
                     std::strcmp(value, "http://192.168.4.1:80"))) {
        reject(403);
        return;
      }
      origin = true;
    } else if (equal_ci(line, "X-P36-Token")) {
      if (token || !copy(token_, sizeof(token_), value)) {
        reject(400);
        return;
      }
      token = true;
    } else if (equal_ci(line, "Content-Type")) {
      if (type || !copy(type_, sizeof(type_), value)) {
        reject(400);
        return;
      }
      type = true;
    }
    line = end + 2;
  }
  if (!host) {
    reject(400);
    return;
  }
  if (!std::strcmp(method_, "POST") && !length) {
    reject(411);
    return;
  }
  if (!std::strcmp(method_, "GET") && expected_) {
    reject(400);
    return;
  }
  if (!std::strcmp(method_, "POST") && expected_) {
    const bool chunk = std::strncmp(target_, "/api/chunk?offset=", 18) == 0;
    if (!type_is(type_,
                 chunk ? "application/octet-stream" : "application/json")) {
      reject(415);
      return;
    }
  }
  state_ = expected_ ? State::Body : State::Complete;
}
bool phone_token_matches(const char *a, const char *b) {
  if (!a || !b || std::strlen(a) != 32 || std::strlen(b) != 32)
    return false;
  unsigned diff = 0;
  for (unsigned i = 0; i < 32; ++i)
    diff |= static_cast<unsigned char>(a[i]) ^ static_cast<unsigned char>(b[i]);
  return diff == 0;
}
bool phone_parse_json(const std::uint8_t *data, std::size_t n, bool need_size,
                      std::uint32_t &size, std::uint32_t &crc) {
  if (!data || n > 128)
    return false;
  std::size_t i = 0;
  bool got_size = false, got_crc = false;
  auto ws = [&]() {
    while (i < n && (data[i] == ' ' || data[i] == '\r' || data[i] == '\n' ||
                     data[i] == '\t'))
      ++i;
  };
  ws();
  if (i == n || data[i++] != '{')
    return false;
  while (true) {
    ws();
    if (i >= n || data[i++] != '"')
      return false;
    char key[8] = {};
    unsigned k = 0;
    while (i < n && data[i] != '"') {
      if (k >= 7)
        return false;
      key[k++] = static_cast<char>(data[i++]);
    }
    if (i >= n)
      return false;
    ++i;
    ws();
    if (i >= n || data[i++] != ':')
      return false;
    ws();
    if (!std::strcmp(key, "size")) {
      if (!need_size || got_size)
        return false;
      char num[12] = {};
      unsigned j = 0;
      while (i < n && data[i] >= '0' && data[i] <= '9') {
        if (j >= 11)
          return false;
        num[j++] = static_cast<char>(data[i++]);
      }
      if (!phone_parse_decimal(num, size))
        return false;
      got_size = true;
    } else if (!std::strcmp(key, "crc")) {
      if (got_crc || i >= n || data[i++] != '"')
        return false;
      std::uint32_t c = 0;
      for (unsigned j = 0; j < 8; ++j) {
        if (i >= n)
          return false;
        char v = lower(static_cast<char>(data[i++]));
        unsigned h = v >= '0' && v <= '9'   ? v - '0'
                     : v >= 'a' && v <= 'f' ? v - 'a' + 10
                                            : 16;
        if (h > 15)
          return false;
        c = (c << 4) | h;
      }
      if (i >= n || data[i++] != '"')
        return false;
      crc = c;
      got_crc = true;
    } else
      return false;
    ws();
    if (i >= n)
      return false;
    if (data[i] == '}') {
      ++i;
      break;
    }
    if (data[i++] != ',')
      return false;
  }
  ws();
  return i == n && got_crc && (!need_size || got_size);
}
} // namespace epd36
