// SPDX-License-Identifier: MIT
#include "phone_service.h"
#include "phone_page.h"
#include "phone_setup_render.h"
#include "portrait_frame.h"
#include <Arduino.h>
#include <cstdio>
#include <cstring>
#include <esp_heap_caps.h>
#include <esp_system.h>
namespace epd36 {
namespace {

void wipe(char *p, std::size_t n) {
  volatile char *v = p;
  while (n--)
    *v++ = 0;
}
const char *reason(unsigned code) {
  switch (code) {
  case 200:
    return "OK";
  case 202:
    return "Accepted";
  case 400:
    return "Bad Request";
  case 401:
    return "Unauthorized";
  case 403:
    return "Forbidden";
  case 404:
    return "Not Found";
  case 405:
    return "Method Not Allowed";
  case 408:
    return "Request Timeout";
  case 409:
    return "Conflict";
  case 411:
    return "Length Required";
  case 413:
    return "Content Too Large";
  case 415:
    return "Unsupported Media Type";
  case 422:
    return "Unprocessable Content";
  case 431:
    return "Request Header Fields Too Large";
  default:
    return "Service Unavailable";
  }
}
} // namespace
void PhoneService::begin() {
  pinMode(UpdatePin, INPUT);
  WiFi.persistent(false);
  WiFi.mode(WIFI_OFF);
  Serial.println(
      "PHONE: hold UPDATE 2s to replace current image with temporary "
      "WiFi credentials; AP is OFF.");
}
void PhoneService::stop() {
  client_.stop();
  server_.end();
  api_.deactivate();
  if (session_.owner() == UploadSource::Phone)
    session_.reset(UploadSource::Phone);
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_OFF);
  active_ = false;
  success_seen_ = false;
  wipe(password_, sizeof(password_));
  wipe(token_, sizeof(token_));
  wipe(ssid_, sizeof(ssid_));
}
bool PhoneService::enable_from_button(std::uint32_t now) {
  if (session_.state() == FrameState::Receiving || api_.queued()) {
    Serial.println(
        "PHONE ERR Busy: finish/reset upload, release UPDATE and hold again");
    return false;
  }
  if (!power_.sample(true).active_allowed) {
    Serial.println("PHONE ERR PowerUnsafe; WiFi not started");
    return false;
  }
  if (active_)
    stop();
  std::uint8_t *frame = nullptr;
  const auto prep = session_.prepare_local_frame(now, frame);
  if (prep != SessionStatus::Ok) {
    Serial.printf("PHONE ERR %s\n", session_status_name(prep));
    return false;
  }
  const auto before = heap_caps_get_free_size(MALLOC_CAP_8BIT);
  Serial.printf(
      "PHONE heap before WiFi: free=%u largest=%u shared_frame=120000 "
      "parser=%u\n",
      static_cast<unsigned>(before),
      static_cast<unsigned>(heap_caps_get_largest_free_block(MALLOC_CAP_8BIT)),
      static_cast<unsigned>(sizeof(request_)));
  if (before < 65536) {
    session_.reset(UploadSource::Phone);
    Serial.println("PHONE ERR NoMemory before WiFi; USB remains available");
    return false;
  }
  // WiFi.mode(AP) starts the RF driver before esp_fill_random; no STA
  // credentials.
  WiFi.persistent(false);
  if (!WiFi.mode(WIFI_AP)) {
    stop();
    Serial.println("PHONE ERR AP start failed");
    return false;
  }
  std::uint8_t random[36];
  esp_fill_random(random, sizeof(random));
  const char *hex = "0123456789ABCDEF";
  const char *alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  std::snprintf(ssid_, sizeof(ssid_), "P36-%02X%02X%02X%02X", random[0],
                random[1], random[2], random[3]);
  for (unsigned i = 0; i < 16; ++i) {
    password_[i] = alphabet[random[4 + i] & 31];
    token_[2 * i] = hex[random[20 + i] >> 4];
    token_[2 * i + 1] = hex[random[20 + i] & 15];
  }
  password_[16] = token_[32] = 0;
  for (volatile std::uint8_t &b : random)
    b = 0;
  if (!WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1),
                         IPAddress(255, 255, 255, 0)) ||
      !WiFi.softAP(ssid_, password_, 1, false, 1)) {
    stop();
    Serial.println("PHONE ERR AP configuration failed");
    return false;
  }
  const auto after = heap_caps_get_free_size(MALLOC_CAP_8BIT);
  Serial.printf(
      "PHONE heap after WiFi: free=%u largest=%u\n",
      static_cast<unsigned>(after),
      static_cast<unsigned>(heap_caps_get_largest_free_block(MALLOC_CAP_8BIT)));
  if (after < 24576 ||
      heap_caps_get_largest_free_block(MALLOC_CAP_8BIT) < 8192) {
    stop();
    Serial.println("PHONE ERR NoMemory after WiFi; AP stopped");
    return false;
  }
  std::uint32_t crc = 0;
  if (!phone_render_setup(frame, kFrameBytes, ssid_, password_, token_) ||
      !portrait::frame_crc32(frame, kFrameBytes, crc) ||
      session_.seal_local_frame(crc, millis()) != SessionStatus::Ok) {
    stop();
    Serial.println("PHONE ERR setup frame invalid");
    return false;
  }
  Serial.println("PHONE replacing image with temporary credentials; refresh "
                 "can take about 15s");
  const auto result = session_.show(UploadSource::Phone, crc, millis());
  if (result != SessionStatus::Ok) {
    Serial.printf(
        "PHONE ERR credentials not confirmed visible: %s / %s; AP stopped\n",
        session_status_name(result),
        result_name(session_.last_display_result()));
    stop();
    return false;
  }
  session_.reset(UploadSource::Phone);
  api_.authorize(token_);
  server_.begin();
  server_.setNoDelay(true);
  active_ = true;
  started_at_ = millis();
  Serial.printf("PHONE AP enabled for 10min. SSID=%s password=%s "
                "URL=http://192.168.4.1/#token=%s\n",
                ssid_, password_, token_);
  Serial.println("PHONE display completed without reported error; visually "
                 "verify credentials on the real panel.");
  return true;
}
void PhoneService::reply(unsigned code, const char *type, const char *body,
                         std::size_t size) {
  char head[512];
  const int n = std::snprintf(
      head, sizeof(head),
      "HTTP/1.1 %u %s\r\nContent-Type: %s\r\nContent-Length: %u\r\nConnection: "
      "close\r\nCache-Control: no-store\r\nX-Content-Type-Options: "
      "nosniff\r\nReferrer-Policy: no-referrer\r\nContent-Security-Policy: "
      "default-src 'self'; script-src 'unsafe-inline'; style-src "
      "'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; "
      "frame-ancestors 'none'\r\n\r\n",
      code, reason(code), type, static_cast<unsigned>(size));
  if (n <= 0 || static_cast<std::size_t>(n) >= sizeof(head)) {
    client_.stop();
    return;
  }
  client_.write(reinterpret_cast<const std::uint8_t *>(head), n);
  for (std::size_t offset = 0; offset < size && client_.connected();) {
    const auto count = (size - offset) > 1024 ? 1024 : (size - offset);
    const auto sent = client_.write(
        reinterpret_cast<const std::uint8_t *>(body + offset), count);
    if (!sent)
      break;
    offset += sent;
    delay(0);
  }
  client_.stop();
}
void PhoneService::process_client(std::uint32_t now) {
  if (!client_) {
    client_ = server_.available();
    if (!client_)
      return;
    client_.setTimeout(1); // WiFiClient uses seconds, request parser separately
                           // bounds total time
    request_.reset(now);
  }
  unsigned count = 0;
  while (client_.available() && count++ < 2048 &&
         request_.state() != PhoneHttpRequest::State::Complete &&
         request_.state() != PhoneHttpRequest::State::Rejected) {
    const int b = client_.read();
    if (b >= 0)
      request_.feed(static_cast<std::uint8_t>(b), now);
  }
  request_.tick(now);
  if (request_.state() == PhoneHttpRequest::State::Rejected) {
    const char *body = "{\"error\":\"InvalidHttpRequest\"}";
    reply(request_.error(), "application/json", body, std::strlen(body));
    return;
  }
  if (request_.state() != PhoneHttpRequest::State::Complete) {
    if (!client_.connected())
      client_.stop();
    return;
  }
  if (!std::strcmp(request_.method(), "GET") &&
      !std::strcmp(request_.target(), "/")) {
    reply(200, "text/html; charset=utf-8", kPhoneIndexHtml,
          std::strlen(kPhoneIndexHtml));
    return;
  }
  char body[256];
  if (!std::strcmp(request_.method(), "POST") &&
      !std::strcmp(request_.target(), "/api/show") &&
      phone_token_matches(request_.token(), token_) &&
      static_cast<std::uint32_t>(now - started_at_) > LifetimeMs - 90000) {
    const char *message = "{\"error\":\"APExpiringSoonHoldUpdateAndReupload\"}";
    reply(409, "application/json", message, std::strlen(message));
    return;
  }
  const auto code = api_.handle(request_, now, body, sizeof(body));
  reply(code, "application/json", body, std::strlen(body));
}
void PhoneService::tick(std::uint32_t now) {
  if (digitalRead(UpdatePin) == LOW) {
    if (!pressing_) {
      pressing_ = true;
      pressed_at_ = now;
    } else if (!latched_ &&
               static_cast<std::uint32_t>(now - pressed_at_) >= 2000) {
      latched_ = true;
      enable_from_button(now);
      now = millis();
    }
  } else {
    pressing_ = false;
    latched_ = false;
  }
  if (!active_)
    return;
  if (!power_.sample().active_allowed) {
    stop();
    Serial.println("PHONE PowerUnsafe; AP stopped");
    return;
  }
  if (static_cast<std::uint32_t>(now - started_at_) >= LifetimeMs) {
    stop();
    Serial.println("PHONE AP expired; hold UPDATE for new credentials");
    return;
  }
  api_.execute_queued(now);
  now = millis();
  if (api_.display_done()) {
    if (!success_seen_) {
      success_seen_ = true;
      success_at_ = now;
    }
    if (static_cast<std::uint32_t>(now - success_at_) >= 30000) {
      stop();
      Serial.println(
          "PHONE display complete; AP closed after 30s result window");
      return;
    }
  } else
    success_seen_ = false;
  if (static_cast<std::uint32_t>(now - started_at_) >= LifetimeMs) {
    stop();
    return;
  }
  process_client(now);
}
} // namespace epd36
