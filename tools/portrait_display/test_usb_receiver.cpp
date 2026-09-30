// SPDX-License-Identifier: MIT
#include "usb_receiver.h"
#include "portrait_frame.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

using epd36::UploadState;
constexpr std::size_t SIZE = epd36::kFrameBytes;
struct FakeIO final : epd36::IO {
    bool powered = false, missing = false, refresh_timeout = false;
    std::uint32_t time = 0, trigger = 0;
    unsigned command = 0, begin_calls = 0, off_calls = 0;
    std::vector<std::uint8_t> frame;
    void hard_off() override { powered = false; ++off_calls; }
    bool begin_bus() override { ++begin_calls; return true; }
    void rail_on() override { powered = true; }
    void reset(bool) override { command = 0; }
    bool write(bool data, std::uint8_t byte) override {
        assert(powered);
        if (!data) { command = byte; trigger = time; }
        else if (command == 0x10) frame.push_back(byte);
        return true;
    }
    bool busy_high() override {
        if (missing) return true;
        if (refresh_timeout && command == 0x12) return false;
        if (command != 0x04 && command != 0x12 && command != 0x02) return true;
        const auto delta = static_cast<std::uint32_t>(time - trigger);
        return delta < 1 || delta >= 3;
    }
    std::uint32_t now_ms() override { return time; }
    void delay_ms(std::uint32_t ms) override { time += ms; }
};
struct Sink final : epd36::UploadSink {
    FakeIO io;
    epd36::Driver driver{io};
    std::vector<std::string> replies;
    // Model only: unchanged unless a complete driver update reports success.
    // This is not evidence about panel pixels after a physical refresh failure.
    std::vector<std::uint8_t> last_success = std::vector<std::uint8_t>(SIZE, 0x11);
    unsigned display_calls = 0;
    bool power_unsafe = false;
    void reply(const char* line) override { replies.emplace_back(line); }
    epd36::Result display(const std::uint8_t* frame, std::size_t size) override {
        ++display_calls;
        if (power_unsafe) { io.hard_off(); return epd36::Result::PowerUnsafe; }
        io.frame.clear();
        const auto result = driver.refresh(frame, size);
        if (result == epd36::Result::Ok) last_success.assign(frame, frame + size);
        assert(!io.powered);
        return result;
    }
};
std::string crc_hex(const std::vector<std::uint8_t>& frame) {
    std::uint32_t crc = 0;
    assert(portrait::frame_crc32(frame.data(), frame.size(), crc));
    char text[9];
    std::snprintf(text, sizeof(text), "%08lX", static_cast<unsigned long>(crc));
    return text;
}
void line(epd36::UsbReceiver& receiver, const std::string& command, std::uint32_t time = 0) {
    for (const auto byte : command + "\n") receiver.feed(static_cast<std::uint8_t>(byte), time);
}
void payload(epd36::UsbReceiver& receiver, const std::vector<std::uint8_t>& bytes,
             std::size_t count = SIZE, std::uint32_t time = 0) {
    for (std::size_t i = 0; i < count; ++i) receiver.feed(bytes[i], time);
}
void stage(epd36::UsbReceiver& receiver, const std::vector<std::uint8_t>& bytes) {
    line(receiver, "RESET");
    line(receiver, "BEGIN 120000 " + crc_hex(bytes));
    assert(receiver.state() == UploadState::Receiving);
    payload(receiver, bytes);
    assert(receiver.state() == UploadState::Ready);
}

int main(int argc, char** argv) {
    std::vector<std::uint8_t> frame(SIZE);
    const std::uint8_t colors[] = {0, 1, 2, 3, 5, 6};
    for (std::size_t i = 0; i < SIZE; ++i) frame[i] = static_cast<std::uint8_t>((colors[i % 6] << 4) | colors[(i + 1) % 6]);
    if (argc == 2) {
        std::ifstream input(argv[1], std::ios::binary);
        assert(input.good());
        frame.assign(std::istreambuf_iterator<char>(input), {});
        assert(frame.size() == SIZE);
    }
    const auto code = crc_hex(frame);
    std::vector<std::uint8_t> storage(SIZE + 2, 0xAC);
    Sink sink;
    epd36::FrameSession session(sink);
    epd36::UsbReceiver receiver(sink, session);
    assert(receiver.bind_buffer(storage.data() + 1, SIZE));
    assert(receiver.state() == UploadState::Empty && sink.display_calls == 0 && !sink.io.powered);
    line(receiver, "HELLO");
    assert(sink.replies.back() == "P36V1 EMPTY");
    stage(receiver, frame);
    assert(sink.display_calls == 0 && sink.io.begin_calls == 0 && sink.replies.back() == "FRAME " + code);
    line(receiver, "SHOW " + code);
    assert(sink.display_calls == 1 && sink.last_success == frame && sink.io.frame == frame);
    assert(sink.replies.back() == "DISPLAY OK " + code && !sink.io.powered);
    const auto good = sink.last_success;
    const auto calls = sink.display_calls;

    std::size_t interruption_cases = 0;
    for (std::size_t stop = 0; stop < SIZE; stop = std::min(SIZE, stop + 256)) {
        line(receiver, "RESET");
        line(receiver, "BEGIN 120000 " + code);
        payload(receiver, frame, stop);
        receiver.tick(3000);
        assert(receiver.state() == UploadState::Fault && sink.replies.back() == "ERR RECEIVE_TIMEOUT RESET_REQUIRED");
        line(receiver, "SHOW " + code, 3000);
        assert(sink.display_calls == calls && sink.last_success == good && !sink.io.powered);
        ++interruption_cases;
    }
    // After full receipt, RESET also drops the pending frame without refreshing.
    stage(receiver, frame);
    line(receiver, "RESET");
    assert(receiver.state() == UploadState::Empty && sink.display_calls == calls);
    for (const auto& header : {"BEGIN 0 12345678", "BEGIN 119999 12345678", "BEGIN 120001 12345678",
                              "BEGIN -120000 12345678", "BEGIN 184467440737095516160 12345678",
                              "BEGIN 120000 1234567", "BEGIN 120000 123456789", "BEGIN 120000 XXXXXXXX",
                              "BEGIN 120000 12345678 extra", "0", "SHOW 12345678"}) {
        line(receiver, "RESET"); line(receiver, header);
        assert(receiver.state() == UploadState::Fault && sink.display_calls == calls);
    }
    line(receiver, "RESET"); line(receiver, std::string(500, 'A'));
    assert(receiver.state() == UploadState::Fault);
    line(receiver, "RESET");
    line(receiver, "BEGIN 120000 " + std::string(code == "00000000" ? "00000001" : "00000000"));
    payload(receiver, frame);
    assert(receiver.state() == UploadState::Fault && sink.replies.back() == "ERR CRC RESET_REQUIRED");
    auto invalid = frame; invalid.back() = 0x44;
    line(receiver, "RESET"); line(receiver, "BEGIN 120000 " + crc_hex(invalid)); payload(receiver, invalid);
    assert(receiver.state() == UploadState::Fault && sink.replies.back() == "ERR INVALID_COLOR RESET_REQUIRED");
    stage(receiver, frame); receiver.feed(0x00, 0); receiver.feed('\n', 0);
    assert(receiver.state() == UploadState::Fault); // overlong binary payload
    line(receiver, "SHOW " + code);
    assert(sink.display_calls == calls && sink.last_success == good);
    stage(receiver, frame); storage[SIZE] ^= 0x01; line(receiver, "SHOW " + code);
    assert(receiver.state() == UploadState::Fault && sink.replies.back() == "ERR FRAME_CHANGED RESET_REQUIRED");
    assert(sink.display_calls == calls);

    // Byte clock wrap, bounded slow trickle, and stalled command handling.
    line(receiver, "RESET", UINT32_MAX - 100);
    line(receiver, "BEGIN 120000 " + code, UINT32_MAX - 100);
    receiver.tick(2899);
    assert(receiver.state() == UploadState::Fault);
    line(receiver, "RESET"); line(receiver, "BEGIN 120000 " + code);
    for (std::uint32_t now = 2000; now < 30000; now += 2000) receiver.feed(0x11, now);
    receiver.tick(30000);
    assert(receiver.state() == UploadState::Fault);
    line(receiver, "RESET"); receiver.feed('H', 0); receiver.tick(1000);
    assert(receiver.state() == UploadState::Fault);
    // Missing/short buffers and restarting with stale RAM never auto-display.
    for (const std::size_t capacity : {std::size_t(0), SIZE - 1}) {
        epd36::FrameSession empty_session(sink);
        epd36::UsbReceiver empty(sink, empty_session);
        assert(!empty.bind_buffer(capacity ? storage.data() + 1 : nullptr, capacity));
        line(empty, "BEGIN 120000 " + code);
        assert(empty.state() == UploadState::Fault && sink.replies.back() == "ERR NO_MEMORY RESET_REQUIRED");
    }
    epd36::FrameSession restarted_session(sink);
    epd36::UsbReceiver restarted(sink, restarted_session);
    assert(restarted.bind_buffer(storage.data() + 1, SIZE));
    line(restarted, "SHOW " + code);
    assert(sink.display_calls == calls && sink.last_success == good);

    // Integrated real driver failures: detached BUSY and refresh timeout cut
    // power and explicitly report unknown physical panel state. RAM permits an
    // explicit SHOW retry, but no automatic retry or refresh on reset occurs.
    stage(receiver, frame); sink.io.missing = true; line(receiver, "SHOW " + code);
    assert(sink.replies.back() == "ERR DISPLAY PowerOnNoAck PANEL_STATE_UNKNOWN" && !sink.io.powered);
    assert(receiver.state() == UploadState::Ready);
    sink.io.missing = false; sink.io.refresh_timeout = true; line(receiver, "SHOW " + code);
    assert(sink.replies.back() == "ERR DISPLAY RefreshTimeout PANEL_STATE_UNKNOWN" && !sink.io.powered);
    sink.io.refresh_timeout = false; line(receiver, "SHOW " + code);
    assert(sink.replies.back() == "DISPLAY OK " + code && sink.io.frame == frame && !sink.io.powered);
    const auto bus_before = sink.io.begin_calls;
    sink.power_unsafe = true; line(receiver, "SHOW " + code);
    assert(sink.replies.back() == "ERR DISPLAY PowerUnsafe NOT_STARTED" && sink.io.begin_calls == bus_before);
    sink.power_unsafe = false;

    // Arbitrary malformed serial input cannot operate hardware after RESET.
    const auto before_fuzz = sink.display_calls;
    line(receiver, "RESET");
    std::uint32_t random = 42;
    for (unsigned i = 0; i < 100000; ++i) {
        random = random * 1664525U + 1013904223U;
        receiver.feed(static_cast<std::uint8_t>(random >> 24), i);
    }
    assert(sink.display_calls == before_fuzz && storage.front() == 0xAC && storage.back() == 0xAC);
    // One buffer, two sources: all cross-source controls are rejected unchanged.
    using Source = epd36::UploadSource;
    using Status = epd36::SessionStatus;
    epd36::FrameSession shared(sink);
    assert(shared.bind_buffer(storage.data() + 1, SIZE));
    std::uint32_t numeric_crc = 0;
    assert(portrait::frame_crc32(frame.data(), SIZE, numeric_crc));
    for (const auto source : {Source::Usb, Source::Phone}) {
        const auto other = source == Source::Usb ? Source::Phone : Source::Usb;
        assert(shared.begin(source, SIZE, numeric_crc, 0) == Status::Ok);
        assert(shared.begin(other, SIZE, numeric_crc, 0) == Status::Busy);
        assert(shared.append(other, 0, frame.data(), 1, 0) == Status::Busy);
        assert(shared.reset(other) == Status::Busy && shared.show(other, numeric_crc, 0) == Status::Busy);
        assert(shared.finish(other) == Status::Busy && shared.received() == 0);
        std::uint8_t* local = nullptr;
        assert(shared.prepare_local_frame(0, local) == Status::Busy && local == nullptr);
        assert(shared.append(source, 1, frame.data(), 1, 0) == Status::BadOffset);
        assert(shared.append(source, 0, nullptr, 1, 0) == Status::NullData);
        assert(shared.append(source, 0, frame.data(), SIZE + 1, 0) == Status::WrongSize);
        assert(shared.append(source, 0, frame.data(), 4096, 0) == Status::Ok);
        assert(shared.append(source, 0, frame.data(), 4096, 0) == Status::BadOffset);
        assert(shared.append(source, 4096, frame.data() + 4096, SIZE - 4096, 0) == Status::Ok);
        assert(shared.finish(source) == Status::Ok && shared.owner() == source);
        assert(shared.reset(other) == Status::Busy && shared.show(other, numeric_crc, 0) == Status::Busy);
        assert(shared.show(source, numeric_crc, 0) == Status::Ok);
        assert(shared.reset(source) == Status::Ok);
    }
    assert(shared.begin(Source::Phone, SIZE, numeric_crc, 0) == Status::Ok);
    epd36::UsbReceiver busy_usb(sink, shared);
    for (const auto& command : {"RESET", "HELLO", "SHOW 00000000", "BEGIN 120000 00000000"}) {
        line(busy_usb, command);
        assert(sink.replies.back() == "ERR BUSY" && shared.owner() == Source::Phone && shared.received() == 0);
    }
    assert(shared.tick(3000) == Status::Timeout && shared.owner() == Source::None);
    assert(shared.begin(Source::Usb, SIZE, numeric_crc, 3000) == Status::Ok);
    assert(shared.append(Source::Usb, 0, frame.data(), SIZE, 3000) == Status::Ok);
    std::uint8_t* local = nullptr;
    assert(shared.prepare_local_frame(3000, local) == Status::Ok && local == storage.data() + 1);
    assert(shared.append(Source::Phone, 0, frame.data(), 1, 3000) == Status::Busy);
    std::copy(frame.begin(), frame.end(), local);
    assert(shared.seal_local_frame(numeric_crc, 3000) == Status::Ok);
    assert(shared.owner() == Source::Phone && shared.show(Source::Phone, numeric_crc, 3000) == Status::Ok);
    assert(shared.tick(123000) == Status::Timeout && shared.owner() == Source::None);
    std::cout << "{\"passed\":true,\"incomplete_receive_boundaries\":" << interruption_cases
              << ",\"malformed_fuzz_bytes\":100000,\"native_frame_bytes\":120000,"
              << "\"driver_spi_equals_uploaded_frame\":true,\"hardware_tested\":false,"
              << "\"source_isolation\":true,\"physical_local_frame_api\":true,\"flash_persistence\":false}\n";
}
