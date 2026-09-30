// SPDX-License-Identifier: MIT
#pragma once
#include "frame_session.h"
#include "phone_http.h"
namespace epd36 {
class PhoneApi {
public:
  explicit PhoneApi(FrameSession &session) : session_(session) {}
  void authorize(const char token[33]);
  void deactivate();
  // Returns HTTP status; serialized response is bounded and contains no
  // secrets.
  unsigned handle(const PhoneHttpRequest &request, std::uint32_t now,
                  char *json, std::size_t capacity);
  void execute_queued(std::uint32_t now);
  bool queued() const { return queued_; }
  bool display_done() const { return display_status_[0] == 'd'; }
  void status_json(char *json, std::size_t capacity) const;

private:
  FrameSession &session_;
  char token_[33] = {};
  bool enabled_ = false, queued_ = false;
  std::uint32_t queued_at_ = 0, queued_crc_ = 0, job_ = 0;
  SessionStatus result_ = SessionStatus::Ok;
  const char *display_status_ = "idle";
};
} // namespace epd36
