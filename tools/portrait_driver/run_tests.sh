#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
VENDOR="${1:-/workspace/scratch/200245c5fbc3/vendor-e-paper/E-paper_Separate_Program/3.6inch_e-Paper_E/ESP32/EPD_3in6e.cpp}"
python3 tools/portrait_driver/make_vendor_oracle.py --vendor "$VENDOR" --out tools/portrait_driver
COMMON=(-std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -g -O1 -Ifirmware/portrait36/include -Itools/portrait_driver)
g++ "${COMMON[@]}" -Ifirmware/include tools/portrait_driver/driver_tests.cpp firmware/portrait36/src/epd_3in6e.cpp firmware/src/portrait_frame.cpp -o tools/portrait_driver/driver-tests-asan
# LSan is unsupported in this ptrace environment; ASan/UBSan remain enabled.
export ASAN_OPTIONS=detect_leaks=0:halt_on_error=1
export UBSAN_OPTIONS=halt_on_error=1
tools/portrait_driver/driver-tests-asan
if [[ -f tools/portrait_display/output/preview400x600/manifest.json ]]; then
  CRC="$(python3 -c 'import json;print(json.load(open("tools/portrait_display/output/preview400x600/manifest.json"))["native_panel_frame"]["crc32_ieee"])')"
  tools/portrait_driver/driver-tests-asan tools/portrait_display/output/preview400x600/panel-3in6e-native.bin "$CRC"
fi
g++ "${COMMON[@]}" -Itools/portrait_driver/arduino_stub tools/portrait_driver/arduino_adapter_tests.cpp firmware/portrait36/src/epd_3in6e.cpp -o tools/portrait_driver/adapter-tests-asan
tools/portrait_driver/adapter-tests-asan
