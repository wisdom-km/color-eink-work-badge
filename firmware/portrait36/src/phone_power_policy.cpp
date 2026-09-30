// SPDX-License-Identifier: MIT
#include "phone_power.h"
namespace epd36 {
PhonePowerSample PhonePowerPolicy::update(std::uint32_t battery_adc_mv,
                                          std::uint32_t vbus_adc_mv) {
  if (vbus_adc_mv >= config_.usb_on_mv)
    usb_ = true;
  else if (vbus_adc_mv <= config_.usb_off_mv)
    usb_ = false;
  const std::uint32_t battery =
      battery_adc_mv > UINT32_MAX / 2 ? UINT32_MAX : battery_adc_mv * 2;
  PhonePowerSample sample;
  sample.battery_mv = battery;
  sample.vbus_sense_mv = vbus_adc_mv;
  sample.usb_present = usb_;
  sample.active_allowed = vbus_adc_mv >= config_.usb_active_mv ||
                          battery >= config_.battery_active_mv;
  return sample;
}
bool PhoneSleepPolicy::should_sleep(std::uint32_t now, bool usb, bool ap,
                                    bool receiving, bool key_low,
                                    bool low_battery, bool display_completed) {
  if (!initialized_) {
    initialized_ = true;
    idle_since_ = now;
  }
  if (key_low) {
    released_ = false;
    idle_since_ = now;
    return false;
  }
  if (!released_) {
    released_ = true;
    released_since_ = now;
  }
  if (usb || ap || receiving) {
    idle_since_ = now;
    return false;
  }
  if (static_cast<std::uint32_t>(now - released_since_) < 100)
    return false;
  return low_battery || display_completed ||
         static_cast<std::uint32_t>(now - idle_since_) >= 60000;
}
} // namespace epd36
