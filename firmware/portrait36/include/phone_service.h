// SPDX-License-Identifier: MIT
#pragma once
#include "phone_api.h"
#include "phone_power.h"
#include <WiFi.h>
namespace epd36 {
class PhoneService {
public:
  explicit PhoneService(FrameSession &session, PhonePowerMonitor &power)
      : session_(session), api_(session), power_(power), server_(80, 1) {}
  void begin();                 // keeps RF/AP OFF; configures UPDATE input only
  void tick(std::uint32_t now); // call only in the same main loop as USB
  bool active() const { return active_; }

private:
  bool enable_from_button(std::uint32_t now);
  void stop();
  void process_client(std::uint32_t now);
  void reply(unsigned code, const char *type, const char *body,
             std::size_t size);
  FrameSession &session_;
  PhoneApi api_;
  PhonePowerMonitor &power_;
  WiFiServer server_;
  WiFiClient client_;
  PhoneHttpRequest request_;
  bool active_ = false, pressing_ = false, latched_ = false;
  std::uint32_t pressed_at_ = 0, started_at_ = 0, success_at_ = 0;
  bool success_seen_ = false;
  char ssid_[16] = {}, password_[17] = {}, token_[33] = {};
  static constexpr std::uint32_t LifetimeMs = 600000;
};
} // namespace epd36
