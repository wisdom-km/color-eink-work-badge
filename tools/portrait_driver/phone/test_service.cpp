// SPDX-License-Identifier: MIT
#include "phone_service.h"
#include "portrait_frame.h"
#include <cassert>
#include <iostream>
#include <vector>
namespace fakephone {
std::uint32_t now = 0, bat_adc = 1900, usb_adc = 0;
bool key_low = false;
std::string serial;
std::deque<std::shared_ptr<Connection>> pending;
bool persistent = true, server_on = false, wifi_ok = true;
int wifi_mode = 0;
unsigned rng_calls = 0;
std::string ssid, password;
std::size_t free_before = 100000, free_after = 50000, largest = 32000;
} // namespace fakephone
FakeSerial Serial;
FakeWiFi WiFi;
struct Sink : epd36::FrameSink {
  unsigned count = 0;
  epd36::Result result = epd36::Result::Ok;
  epd36::Result display(const std::uint8_t *p, std::size_t n) override {
    ++count;
    std::uint32_t crc = 0;
    assert(portrait::frame_crc32(p, n, crc));
    assert(portrait::validate_3in6e_frame(p, n, crc) ==
           portrait::FrameStatus::Valid);
    return result;
  }
};
unsigned cases = 0;
void hold(epd36::PhoneService &p) {
  fakephone::key_low = false;
  p.tick(fakephone::now);
  fakephone::key_low = true;
  p.tick(fakephone::now);
  fakephone::now += 1999;
  p.tick(fakephone::now);
  fakephone::now += 1;
  p.tick(fakephone::now);
  fakephone::key_low = false;
  p.tick(fakephone::now);
}
int main() {
  using namespace epd36;
  assert(UpdatePin == 1 && VbusSensePin == 4 && BatterySensePin == 0 &&
         UpdateWakeMask == 2);
  ++cases;
  PhonePowerPolicy powerpolicy;
  auto s = powerpolicy.update(1800, 599);
  assert(!s.usb_present && s.active_allowed && s.battery_mv == 3600);
  ++cases;
  s = powerpolicy.update(1700, 600);
  assert(s.usb_present && !s.active_allowed);
  s = powerpolicy.update(1700, 550);
  assert(s.usb_present);
  s = powerpolicy.update(1700, 500);
  assert(!s.usb_present);
  ++cases;
  s = powerpolicy.update(0, 1240);
  assert(s.usb_present && s.active_allowed);
  ++cases;
  s = powerpolicy.update(1799, 0);
  assert(!s.active_allowed);
  ++cases;
  {
    PhoneSleepPolicy p;
    assert(!p.should_sleep(0, false, false, false, false, false));
    assert(!p.should_sleep(59999, false, false, false, false, false));
    assert(p.should_sleep(60000, false, false, false, false, false));
    ++cases;
  }
  {
    PhoneSleepPolicy p;
    assert(!p.should_sleep(0, false, false, false, true, true));
    assert(!p.should_sleep(600000, false, false, false, true, true));
    assert(!p.should_sleep(600001, false, false, false, false, true));
    assert(!p.should_sleep(600100, false, false, false, false, true));
    assert(p.should_sleep(600101, false, false, false, false, true));
    ++cases;
  }
  {
    PhoneSleepPolicy p;
    for (unsigned t : {0u, 60000u, 900000u}) {
      assert(!p.should_sleep(t, true, false, false, false, true, true));
      assert(!p.should_sleep(t, false, true, false, false, true, true));
      assert(!p.should_sleep(t, false, false, true, false, true, true));
    }
    ++cases;
  }
  {
    PhoneSleepPolicy p;
    p.should_sleep(UINT32_MAX - 200, false, false, false, false, false);
    assert(p.should_sleep(59900, false, false, false, false, false));
    ++cases;
  }
  std::vector<std::uint8_t> frame(kFrameBytes);
  Sink sink;
  FrameSession session(sink);
  assert(session.bind_buffer(frame.data(), frame.size()));
  PhonePowerMonitor power;
  power.begin();
  PhoneService phone(session, power);
  phone.begin();
  assert(!phone.active() && !fakephone::server_on &&
         fakephone::wifi_mode == WIFI_OFF && !fakephone::persistent);
  ++cases;
  fakephone::key_low = true;
  phone.tick(fakephone::now);
  fakephone::now += 1999;
  phone.tick(fakephone::now);
  assert(!phone.active() && sink.count == 0);
  ++cases;
  fakephone::now += 1;
  phone.tick(fakephone::now);
  assert(phone.active() && sink.count == 1 && fakephone::server_on);
  assert(session.owner() == UploadSource::None);
  const auto first_password = fakephone::password;
  const auto first_name = fakephone::ssid;
  ++cases;
  fakephone::now += 100;
  phone.tick(fakephone::now);
  assert(sink.count == 1);
  fakephone::key_low = false;
  phone.tick(fakephone::now);
  ++cases;
  auto page = std::make_shared<fakephone::Connection>();
  page->in = "GET / HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n";
  fakephone::pending.push_back(page);
  phone.tick(fakephone::now);
  assert(page->out.find("HTTP/1.1 200 OK") != std::string::npos &&
         page->out.find("Content-Security-Policy") != std::string::npos &&
         page->out.size() > 18000);
  assert(page->out.find(first_password) == std::string::npos);
  ++cases;
  auto auth = std::make_shared<fakephone::Connection>();
  auth->in = "GET /api/status HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n";
  fakephone::pending.push_back(auth);
  phone.tick(fakephone::now);
  assert(auth->out.find("401 Unauthorized") != std::string::npos);
  ++cases;
  fakephone::now += 600000;
  phone.tick(fakephone::now);
  assert(!phone.active() && !fakephone::server_on &&
         fakephone::wifi_mode == WIFI_OFF);
  ++cases;
  hold(phone);
  assert(phone.active() && fakephone::password != first_password &&
         fakephone::ssid != first_name);
  ++cases;
  fakephone::bat_adc = 1700;
  fakephone::now += 600;
  phone.tick(fakephone::now);
  assert(!phone.active());
  ++cases;
  const auto count = sink.count;
  hold(phone);
  assert(!phone.active() && sink.count == count);
  ++cases;
  fakephone::bat_adc = 1900;
  fakephone::free_before = 60000;
  fakephone::now += 600;
  hold(phone);
  assert(!phone.active() && sink.count == count);
  ++cases;
  fakephone::free_before = 100000;
  fakephone::free_after = 20000;
  hold(phone);
  assert(!phone.active() && fakephone::wifi_mode == WIFI_OFF &&
         sink.count == count);
  ++cases;
  fakephone::free_after = 50000;
  sink.result = Result::RefreshTimeout;
  hold(phone);
  assert(!phone.active() && fakephone::wifi_mode == WIFI_OFF &&
         sink.count == count + 1);
  ++cases;
  sink.result = Result::Ok;
  assert(session.begin(UploadSource::Usb, kFrameBytes, 0, fakephone::now) ==
         SessionStatus::Ok);
  hold(phone);
  assert(!phone.active() && session.owner() == UploadSource::Usb);
  ++cases;
  std::cout << "{\"service_power_model_cases\":" << cases
            << ",\"wake_gpio\":1,\"wake_mask\":2,\"usb_adc_gpio\":4,\"no_real_"
               "wifi_or_gpio\":true}\n";
}
