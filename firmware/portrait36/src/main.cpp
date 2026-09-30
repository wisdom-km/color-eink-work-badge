// SPDX-License-Identifier: MIT
// Isolated USB full-frame diagnostic target; never substitute for H2 firmware.
#include "arduino_io.h"
#include "phone_service.h"
#include "usb_receiver.h"
#include <driver/gpio.h>
#include <esp_heap_caps.h>
#include <esp_sleep.h>
namespace {
epd36::c3::ArduinoIO io;
epd36::Driver driver(io);
epd36::PhonePowerMonitor power;
epd36::PhoneSleepPolicy sleep_policy;
bool display_completed = false;
class SerialSink final : public epd36::UploadSink {
public:
  void reply(const char *line) override {
    Serial.println(line);
    Serial.flush();
  }
  epd36::Result display(const std::uint8_t *frame, std::size_t size) override {
    const auto reading = power.sample(true);
    Serial.printf("POWER VBAT=%umV VBUS_SENSE=%umV USB=%u\n",
                  static_cast<unsigned>(reading.battery_mv),
                  static_cast<unsigned>(reading.vbus_sense_mv),
                  reading.usb_present);
    if (!reading.active_allowed) {
      io.hard_off();
      return epd36::Result::PowerUnsafe;
    }
    const auto result = driver.refresh(frame, size);
    if (result == epd36::Result::Ok)
      display_completed = true;
    return result;
  }
} sink;
epd36::FrameSession frame_session(sink);
epd36::UsbReceiver receiver(sink, frame_session);
epd36::PhoneService phone(frame_session, power);
std::uint8_t *pending_frame =
    nullptr; // one allocation, retained until MCU reset
} // namespace
void setup() {
  io.hard_off();
  gpio_hold_dis(GPIO_NUM_2);
  gpio_deep_sleep_hold_dis();
  io.hard_off();
  Serial.setRxBufferSize(4096);
  Serial.begin(115200);
  delay(100);
  Serial.println("P36 USB + local phone update; rail OFF; no automatic "
                 "refresh. RESET then HELLO.");
  Serial.println("New 50-pin 3.6E panel PCB only; not H2. USB presence is not "
                 "a voltage measurement.");
  Serial.printf(
      "heap_free=%u largest_8bit_block=%u frame_bytes=%u\n",
      static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_8BIT)),
      static_cast<unsigned>(heap_caps_get_largest_free_block(MALLOC_CAP_8BIT)),
      static_cast<unsigned>(epd36::kFrameBytes));
  power.begin();
  phone.begin();
  pending_frame = static_cast<std::uint8_t *>(
      heap_caps_malloc(epd36::kFrameBytes, MALLOC_CAP_8BIT));
  if (!receiver.bind_buffer(pending_frame,
                            pending_frame ? epd36::kFrameBytes : 0)) {
    Serial.println("ERR NO_MEMORY; rail OFF; uploads disabled until restart");
  }
}
void loop() {
  phone.tick(millis());
  // Bound each batch so watchdog/USB tasks and timeout checks keep running.
  for (unsigned i = 0; i < 2048 && Serial.available(); ++i) {
    const int byte = Serial.read();
    if (byte >= 0)
      receiver.feed(static_cast<std::uint8_t>(byte), millis());
  }
  receiver.tick(millis());
  const auto reading = power.sample();
  const auto now = millis();
  if (sleep_policy.should_sleep(now, reading.usb_present, phone.active(),
                                frame_session.state() ==
                                    epd36::FrameState::Receiving,
                                digitalRead(epd36::UpdatePin) == LOW,
                                !reading.active_allowed, display_completed)) {
    // UPDATE is stable HIGH before enabling LOW wake; avoids a reset/wake loop.
    io.hard_off();
    esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
    const auto wake_result = esp_deep_sleep_enable_gpio_wakeup(
        epd36::UpdateWakeMask, ESP_GPIO_WAKEUP_GPIO_LOW);
    if (wake_result == ESP_OK && gpio_hold_en(GPIO_NUM_2) == ESP_OK) {
      gpio_deep_sleep_hold_en();
      Serial.println("SLEEP: screen rail OFF; short UPDATE wakes USB, hold 2s "
                     "for phone. USB insertion alone is not a wake source.");
      Serial.flush();
      esp_deep_sleep_start();
    } else {
      Serial.printf("ERR WAKE_SETUP %d; refusing sleep\n",
                    static_cast<int>(wake_result));
      delay(1000);
    }
  }
  delay(1);
}
