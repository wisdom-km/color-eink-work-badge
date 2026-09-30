// SPDX-License-Identifier: MIT
#include "phone_api.h"
#include <cstdio>
#include <cstring>
namespace epd36 {
namespace {
unsigned http_status(SessionStatus s) {
  switch (s) {
  case SessionStatus::Ok:
    return 200;
  case SessionStatus::Busy:
  case SessionStatus::BadOffset:
    return 409;
  case SessionStatus::NoMemory:
    return 503;
  case SessionStatus::Timeout:
    return 408;
  case SessionStatus::DisplayFailed:
    return 500;
  default:
    return 422;
  }
}
void clear_secret(char *p, std::size_t n) {
  volatile char *v = p;
  while (n--)
    *v++ = 0;
}
} // namespace
void PhoneApi::authorize(const char token[33]) {
  deactivate();
  if (token && std::strlen(token) == 32) {
    std::memcpy(token_, token, 33);
    enabled_ = true;
  }
}
void PhoneApi::deactivate() {
  enabled_ = false;
  queued_ = false;
  clear_secret(token_, sizeof(token_));
  display_status_ = "idle";
  result_ = SessionStatus::Ok;
}
void PhoneApi::status_json(char *out, std::size_t n) const {
  const char *state = session_.state() == FrameState::Ready       ? "Ready"
                      : session_.state() == FrameState::Receiving ? "Receiving"
                                                                  : "Empty";
  const char *owner = session_.owner() == UploadSource::Phone ? "Phone"
                      : session_.owner() == UploadSource::Usb ? "Usb"
                                                              : "None";
  std::snprintf(out, n,
                "{\"state\":\"%s\",\"owner\":\"%s\",\"received\":%u,\"crc\":\"%"
                "08X\",\"result\":\"%s\",\"display_status\":\"%s\",\"job\":%u,"
                "\"driver_result\":\"%s\"}",
                state, owner, static_cast<unsigned>(session_.received()),
                static_cast<unsigned>(session_.crc()),
                session_status_name(result_), display_status_,
                static_cast<unsigned>(job_),
                result_name(session_.last_display_result()));
}
unsigned PhoneApi::handle(const PhoneHttpRequest &r, std::uint32_t now,
                          char *out, std::size_t cap) {
  if (!enabled_ || !phone_token_matches(r.token(), token_)) {
    std::snprintf(out, cap, "{\"error\":\"Unauthorized\"}");
    return 401;
  }
  if (session_.tick(now) == SessionStatus::Timeout)
    result_ = SessionStatus::Timeout;
  if (!std::strcmp(r.method(), "GET") &&
      !std::strcmp(r.target(), "/api/status")) {
    status_json(out, cap);
    return 200;
  }
  if (std::strcmp(r.method(), "POST")) {
    std::snprintf(out, cap, "{\"error\":\"NotFound\"}");
    return 404;
  }
  if (queued_) {
    std::snprintf(out, cap, "{\"error\":\"Busy\"}");
    return 409;
  }
  unsigned code = 200;
  std::uint32_t size = 0, crc = 0;
  if (!std::strcmp(r.target(), "/api/begin")) {
    if (!phone_parse_json(r.body(), r.size(), true, size, crc)) {
      std::snprintf(out, cap, "{\"error\":\"BadJson\"}");
      return 400;
    }
    result_ = session_.begin(UploadSource::Phone, size, crc, now);
    if (result_ == SessionStatus::Ok)
      display_status_ = "idle";
  } else if (!std::strncmp(r.target(), "/api/chunk?offset=", 18)) {
    std::uint32_t offset = 0;
    if (!phone_parse_decimal(r.target() + 18, offset)) {
      std::snprintf(out, cap, "{\"error\":\"BadOffset\"}");
      return 400;
    }
    if (r.size() == 0 || r.size() > PhoneHttpRequest::BodyLimit) {
      std::snprintf(out, cap, "{\"error\":\"WrongSize\"}");
      return 413;
    }
    result_ =
        session_.append(UploadSource::Phone, offset, r.body(), r.size(), now);
  } else if (!std::strcmp(r.target(), "/api/show")) {
    if (!phone_parse_json(r.body(), r.size(), false, size, crc)) {
      std::snprintf(out, cap, "{\"error\":\"BadJson\"}");
      return 400;
    }
    result_ = session_.finish(UploadSource::Phone);
    if (result_ == SessionStatus::Ok && session_.crc() != crc)
      result_ = SessionStatus::CrcMismatch;
    if (result_ == SessionStatus::Ok) {
      queued_ = true;
      queued_crc_ = crc;
      queued_at_ = now;
      ++job_;
      display_status_ = "queued";
      code = 202;
    }
  } else if (!std::strcmp(r.target(), "/api/reset")) {
    if (r.size() != 0) {
      std::snprintf(out, cap, "{\"error\":\"UnexpectedBody\"}");
      return 400;
    }
    result_ = session_.reset(UploadSource::Phone);
    if (result_ == SessionStatus::Ok)
      display_status_ = "idle";
  } else {
    std::snprintf(out, cap, "{\"error\":\"NotFound\"}");
    return 404;
  }
  if (result_ != SessionStatus::Ok)
    code = http_status(result_);
  status_json(out, cap);
  return code;
}
void PhoneApi::execute_queued(std::uint32_t now) {
  if (!enabled_ || !queued_ ||
      static_cast<std::uint32_t>(now - queued_at_) < 200)
    return;
  display_status_ = "refreshing";
  result_ = session_.show(UploadSource::Phone, queued_crc_, now);
  queued_ = false;
  display_status_ = result_ == SessionStatus::Ok ? "done" : "failed";
}
} // namespace epd36
