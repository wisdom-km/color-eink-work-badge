// SPDX-License-Identifier: MIT
#include "phone_power.h"
#include <Arduino.h>
namespace epd36 {
void PhonePowerMonitor::begin() {
  pinMode(VbusSensePin, INPUT);
  pinMode(BatterySensePin, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(VbusSensePin, ADC_11db);
  analogSetPinAttenuation(BatterySensePin, ADC_11db);
  delay(100); // 1M/330k with 100n: ~25ms RC, allow >=4 time constants
  sample(true);
}
PhonePowerSample PhonePowerMonitor::sample(bool force) {
  const auto now = millis();
  if (!force && sampled_ && static_cast<std::uint32_t>(now - last_at_) < 500)
    return last_;
  std::uint32_t bat = 0, usb = 0;
  for (unsigned i = 0; i < 8; ++i) {
    bat += analogReadMilliVolts(BatterySensePin);
    usb += analogReadMilliVolts(VbusSensePin);
    delay(2);
  }
  last_ = policy_.update(bat / 8, usb / 8);
  last_at_ = millis();
  sampled_ = true;
  return last_;
}
} // namespace epd36
