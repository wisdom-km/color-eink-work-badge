#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=tools/portrait_display/output/usb-tests
mkdir -p "$OUT"
g++ -std=c++17 -O1 -g -Wall -Wextra -Werror -Wconversion -Wsign-conversion \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  -Ifirmware/include -Ifirmware/portrait36/include \
  tools/portrait_display/test_usb_receiver.cpp firmware/portrait36/src/usb_receiver.cpp firmware/portrait36/src/frame_session.cpp \
  firmware/portrait36/src/epd_3in6e.cpp firmware/src/portrait_frame.cpp \
  -o "$OUT/receiver-tests" > "$OUT/compile.log" 2>&1
export ASAN_OPTIONS=detect_leaks=0:halt_on_error=1
export UBSAN_OPTIONS=halt_on_error=1
"$OUT/receiver-tests" > "$OUT/parser-tests.json"
"$OUT/receiver-tests" tools/portrait_display/output/preview400x600/panel-3in6e-native.bin > "$OUT/native-sample-tests.json"
PYTHONPATH=tools/portrait_display python -m unittest -v test_sender > "$OUT/sender-tests.log" 2>&1
python tools/portrait_display/send_frame.py --dry-run \
  tools/portrait_display/output/preview400x600/panel-3in6e-native.bin > "$OUT/sender-dry-run.json"
python -m py_compile tools/portrait_display/*.py
cat "$OUT/parser-tests.json" "$OUT/native-sample-tests.json" "$OUT/sender-tests.log" "$OUT/sender-dry-run.json"
