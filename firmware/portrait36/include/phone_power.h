// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>
namespace epd36 {
constexpr int UpdatePin = 1, VbusSensePin = 4, BatterySensePin = 0;
constexpr std::uint64_t UpdateWakeMask = std::uint64_t(1) << UpdatePin;
struct PhonePowerConfig {
  std::uint32_t usb_on_mv = 600, usb_off_mv = 500;
  std::uint32_t usb_active_mv = 1000; // ~4.03 V before 1M/330k divider
  std::uint32_t battery_active_mv =
      3600; // conservative, must be calibrated on hardware
};
struct PhonePowerSample {
  std::uint32_t battery_mv = 0, vbus_sense_mv = 0;
  bool usb_present = false, active_allowed = false;
};
class PhonePowerPolicy {
public:
  explicit PhonePowerPolicy(PhonePowerConfig config = {}) : config_(config) {}
  PhonePowerSample update(std::uint32_t battery_adc_mv,
                          std::uint32_t vbus_adc_mv);

private:
  PhonePowerConfig config_;
  bool usb_ = false;
};
class PhonePowerMonitor {
public:
  explicit PhonePowerMonitor(PhonePowerConfig config = {}) : policy_(config) {}
  void begin();
  PhonePowerSample sample(bool force = false);

private:
  PhonePowerPolicy policy_;
  PhonePowerSample last_;
  std::uint32_t last_at_ = 0;
  bool sampled_ = false;
};
// Model for idle sleep admission; never sleep with UPDATE still held LOW.
class PhoneSleepPolicy {
public:
  bool should_sleep(std::uint32_t now, bool usb, bool ap, bool receiving,
                    bool key_low, bool low_battery,
                    bool display_completed = false);

private:
  bool initialized_ = false, released_ = false;
  std::uint32_t idle_since_ = 0, released_since_ = 0;
};
} // namespace epd36
