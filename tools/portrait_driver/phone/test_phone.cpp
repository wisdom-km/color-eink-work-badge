// SPDX-License-Identifier: MIT
#include "phone_api.h"
#include "phone_http.h"
#include "phone_setup_render.h"
#include "portrait_frame.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
using namespace epd36;
const char *token = "0123456789ABCDEF0123456789ABCDEF";
unsigned cases = 0;
struct Sink : FrameSink {
  unsigned calls = 0;
  Result next = Result::Ok;
  std::uint32_t seen_crc = 0;
  Result display(const std::uint8_t *p, std::size_t n) override {
    ++calls;
    assert(n == kFrameBytes);
    assert(portrait::frame_crc32(p, n, seen_crc));
    return next;
  }
};
std::string hex(std::uint32_t n) {
  char b[9];
  std::snprintf(b, sizeof(b), "%08X", static_cast<unsigned>(n));
  return b;
}
std::string begin_json(std::uint32_t crc) {
  return "{\"size\":120000,\"crc\":\"" + hex(crc) + "\"}";
}
std::string request(const std::string &method, const std::string &target,
                    const std::string &body = "", const char *auth = token) {
  std::string s = method + " " + target + " HTTP/1.1\r\nHost: 192.168.4.1\r\n";
  if (auth)
    s += "X-P36-Token: " + std::string(auth) + "\r\n";
  if (method == "POST")
    s += "Content-Length: " + std::to_string(body.size()) +
         "\r\nContent-Type: " +
         (target.find("/api/chunk?") == 0 ? "application/octet-stream"
                                          : "application/json") +
         "\r\n";
  return s + "\r\n" + body;
}
PhoneHttpRequest parse(const std::string &wire, std::uint32_t now = 0) {
  PhoneHttpRequest p;
  p.reset(now);
  for (unsigned char c : wire)
    p.feed(c, now);
  return p;
}
void rejection(const std::string &wire, unsigned status) {
  auto p = parse(wire);
  assert(p.state() == PhoneHttpRequest::State::Rejected && p.error() == status);
  ++cases;
}
unsigned call(PhoneApi &a, const std::string &path, const std::string &body,
              char *out, std::uint32_t now = 0, const char *auth = token,
              const char *method = "POST") {
  auto p = parse(request(method, path, body, auth), now);
  assert(p.state() == PhoneHttpRequest::State::Complete);
  return a.handle(p, now, out, 256);
}
void send_all(PhoneApi &a, const std::vector<std::uint8_t> &f, char *out,
              std::uint32_t now = 10, unsigned last_status = 200) {
  for (std::size_t i = 0; i < f.size(); i += 4096) {
    const auto n = std::min<std::size_t>(4096, f.size() - i);
    const std::string body(reinterpret_cast<const char *>(f.data() + i), n);
    assert(call(a, "/api/chunk?offset=" + std::to_string(i), body, out,
                now + (i / 4096)) == (i + n == f.size() ? last_status : 200));
  }
}
int main() {
  rejection("POST /api/chunk?offset=0 HTTP/1.1\r\nHost: "
            "192.168.4.1\r\nContent-Length: 120000\r\n\r\n",
            413);
  rejection("POST /api/begin HTTP/1.1\r\nHost: 192.168.4.1\r\nContent-Length: "
            "4294967296\r\n\r\n",
            400);
  rejection("POST /api/reset HTTP/1.1\r\nHost: 192.168.4.1\r\nContent-Length: "
            "0\r\nContent-Length: 0\r\n\r\n",
            400);
  rejection("POST /api/reset HTTP/1.1\r\nHost: "
            "192.168.4.1\r\nTransfer-Encoding: chunked\r\n\r\n",
            400);
  rejection("POST /api/reset HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n", 411);
  rejection("GET / HTTP/1.1\r\nHost: 192.168.4.1\r\nContent-Length: 1\r\n\r\nx",
            400);
  rejection("GET / HTTP/1.1\r\nHost: attacker.test\r\n\r\n", 400);
  rejection("GET / HTTP/1.1\r\nHost: 192.168.4.1\r\nOrigin: "
            "http://attacker.test\r\n\r\n",
            403);
  rejection("GET / HTTP/1.1\r\nHost: 192.168.4.1\r\nX-P36-Token: "
            "a\r\nx-p36-token: b\r\n\r\n",
            400);
  rejection("GET / HTTP/1.1\r\nHost: 192.168.4.1\r\nX-Fill: " +
                std::string(2100, 'a') + "\r\n\r\n",
            431);
  rejection(std::string("GET / HTTP/1.1\r\nH\0ost: x\r\n\r\n",
                        sizeof("GET / HTTP/1.1\r\nH\0ost: x\r\n\r\n") - 1),
            400);
  {
    auto p = parse("GET / HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n");
    assert(p.state() == PhoneHttpRequest::State::Complete);
    ++cases;
  }
  {
    PhoneHttpRequest p;
    p.reset(UINT32_MAX - 2500);
    p.feed('G', UINT32_MAX - 2500);
    assert(p.tick(2499) == PhoneHttpRequest::State::Rejected &&
           p.error() == 408);
    ++cases;
  }
  {
    auto p = parse("POST /api/chunk?offset=0 HTTP/1.1\r\nHost: "
                   "192.168.4.1\r\nContent-Type: "
                   "application/octet-stream\r\nContent-Length: 4\r\n\r\nab");
    assert(p.tick(5000) == PhoneHttpRequest::State::Rejected &&
           p.error() == 408);
    ++cases;
  }
  {
    std::uint32_t size = 0, crc = 0;
    for (const auto &s :
         {"{}", "{\"size\":-1,\"crc\":\"12345678\"}",
          "{\"size\":120000,\"crc\":\"1234567\"}",
          "{\"crc\":\"12345678\",\"crc\":\"12345678\",\"size\":120000}",
          "{\"size\":120000,\"x\":0,\"crc\":\"12345678\"}"}) {
      assert(!phone_parse_json(reinterpret_cast<const std::uint8_t *>(s),
                               std::strlen(s), true, size, crc));
      ++cases;
    }
  }
  std::vector<std::uint8_t> f(kFrameBytes, 0x11), buf(kFrameBytes);
  std::uint32_t crc = 0;
  assert(portrait::frame_crc32(f.data(), f.size(), crc));
  char out[256];
  Sink sink;
  FrameSession session(sink);
  assert(session.bind_buffer(buf.data(), buf.size()));
  PhoneApi api(session);
  api.authorize(token);
  assert(call(api, "/api/begin", begin_json(crc), out, 0, "BAD") == 401);
  assert(session.owner() == UploadSource::None);
  ++cases;
  assert(session.begin(UploadSource::Usb, kFrameBytes, crc, 0) ==
         SessionStatus::Ok);
  for (const auto &path :
       {"/api/begin", "/api/reset", "/api/show", "/api/chunk?offset=0"}) {
    const std::string body = std::string(path) == "/api/begin" ? begin_json(crc)
                             : std::string(path) == "/api/show"
                                 ? "{\"crc\":\"" + hex(crc) + "\"}"
                             : std::string(path) == "/api/reset" ? ""
                                                                 : "x";
    assert(call(api, path, body, out) == 409);
    assert(session.owner() == UploadSource::Usb && session.received() == 0);
    ++cases;
  }
  session.reset(UploadSource::Usb);
  assert(call(api, "/api/begin", begin_json(crc), out) == 200);
  assert(session.begin(UploadSource::Usb, kFrameBytes, crc, 0) ==
         SessionStatus::Busy);
  ++cases;
  assert(call(api, "/api/chunk?offset=1", "x", out) == 409);
  assert(session.received() == 0);
  ++cases;
  assert(call(api, "/api/chunk?offset=0", "", out) == 413);
  ++cases;
  send_all(api, f, out);
  assert(session.state() == FrameState::Ready && sink.calls == 0);
  ++cases;
  assert(call(api, "/api/show", "{\"crc\":\"00000000\"}", out, 50) == 422 &&
         sink.calls == 0);
  ++cases;
  assert(call(api, "/api/show", "{\"crc\":\"" + hex(crc) + "\"}", out, 50) ==
             202 &&
         sink.calls == 0);
  assert(std::strstr(out, "queued"));
  ++cases;
  assert(call(api, "/api/reset", "", out, 51) == 409);
  assert(session.reset(UploadSource::Usb) == SessionStatus::Busy);
  ++cases;
  api.execute_queued(249);
  assert(sink.calls == 0);
  api.execute_queued(250);
  assert(sink.calls == 1 && sink.seen_crc == crc);
  api.execute_queued(500);
  assert(sink.calls == 1);
  ++cases;
  assert(call(api, "/api/status", "", out, 500, token, "GET") == 200);
  assert(std::strstr(out, "\"display_status\":\"done\"") &&
         std::strstr(out, "\"job\":1") &&
         std::strstr(out, "\"result\":\"Ok\""));
  ++cases;
  assert(call(api, "/api/reset", "", out, 501) == 200);
  assert(call(api, "/api/begin", begin_json(crc ^ 1), out, 502) == 200);
  send_all(api, f, out, 510, 422);
  assert(session.state() == FrameState::Empty && sink.calls == 1);
  ++cases;
  assert(call(api, "/api/begin", begin_json(crc), out, 550) == 200);
  auto invalid = f;
  invalid.back() = 0x44;
  send_all(api, invalid, out, 560, 422);
  assert(session.state() == FrameState::Empty);
  ++cases;
  assert(call(api, "/api/begin", begin_json(crc), out, 600) == 200);
  send_all(api, f, out, 610);
  buf[0] = 0;
  assert(call(api, "/api/show", "{\"crc\":\"" + hex(crc) + "\"}", out, 650) ==
         202);
  api.execute_queued(850);
  assert(sink.calls == 1 && session.state() == FrameState::Empty);
  api.status_json(out, sizeof(out));
  assert(std::strstr(out, "FrameChanged") && std::strstr(out, "failed"));
  ++cases;
  assert(call(api, "/api/begin", begin_json(crc), out, 900) == 200);
  send_all(api, f, out, 910);
  sink.next = Result::RefreshTimeout;
  assert(call(api, "/api/show", "{\"crc\":\"" + hex(crc) + "\"}", out, 950) ==
         202);
  api.execute_queued(1150);
  api.status_json(out, sizeof(out));
  assert(sink.calls == 2 && std::strstr(out, "DisplayFailed") &&
         std::strstr(out, "failed"));
  ++cases;
  api.deactivate();
  assert(call(api, "/api/status", "", out, 1200, token, "GET") == 401);
  ++cases;
  api.authorize(token);
  session.reset(UploadSource::Phone);
  assert(call(api, "/api/begin", begin_json(crc), out, 1300) == 200);
  session.tick(4300);
  assert(call(api, "/api/chunk?offset=0", "x", out, 4301) == 422 &&
         session.owner() == UploadSource::None);
  ++cases;
  // Setup page has deterministic sparse colors, bounded writes, differing
  // secrets.
  std::vector<std::uint8_t> page(kFrameBytes + 16, 0xA7);
  assert(phone_render_setup(page.data(), kFrameBytes, "P36-1234ABCD",
                            "ABCDEFGH23456789", token));
  assert(std::all_of(page.begin() + kFrameBytes, page.end(),
                     [](auto b) { return b == 0xA7; }));
  for (std::size_t i = 0; i < kFrameBytes; ++i)
    assert((page[i] & 15) <= 1 && (page[i] >> 4) <= 1);
  assert(std::count(page.begin(), page.begin() + kFrameBytes, 0x11) < 119000);
  ++cases;
  const auto good = page;
  assert(
      !phone_render_setup(page.data(), kFrameBytes - 1, "P36-X", "ABC", token));
  assert(page == good);
  ++cases;
  assert(!phone_render_setup(page.data(), kFrameBytes, "P36-X", "bad secret",
                             token));
  assert(page == good);
  ++cases;
  assert(phone_render_setup(page.data(), kFrameBytes, "P36-ABCD1234",
                            "ABCDEFGH23456789",
                            "FEDCBA9876543210FEDCBA9876543210"));
  assert(page != good);
  ++cases;
  std::cout << "{\"phone_host_cases\":" << cases
            << ",\"header_limit\":2048,\"body_limit\":4096,\"parser_bytes\":"
            << sizeof(PhoneHttpRequest)
            << ",\"one_frame_bytes\":120000,\"no_hardware_or_network\":true}\n";
}
