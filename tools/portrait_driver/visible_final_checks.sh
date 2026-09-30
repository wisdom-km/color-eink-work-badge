#!/usr/bin/env bash
set -euo pipefail
set -x
cd /workspace/scratch/200245c5fbc3/chroma-badge
source tools/portrait_environment/env.sh
OUT=hardware/portrait/verification/visible-final
mkdir -p "$OUT"
export ASAN_OPTIONS=detect_leaks=0:halt_on_error=1
export UBSAN_OPTIONS=halt_on_error=1
node tools/portrait_display/phone/test_app.js | tee "$OUT/phone-dom.json"
node tools/portrait_display/phone/test_core.js tools/portrait_display/output/preview400x600/portrait.rgba tools/portrait_display/output/preview400x600/panel-3in6e-native.bin | tee "$OUT/phone-core.json"
python3 tools/portrait_display/build_phone_page.py
python3 tools/portrait_display/run_tests.py --out "$OUT/frame"
bash tools/portrait_display/run_usb_tests.sh 2>&1 | tee "$OUT/usb.log"
bash tools/portrait_driver/run_tests.sh 2>&1 | tee "$OUT/driver.log"
CXX=(-std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -g -O1 -Ifirmware/portrait36/include -Ifirmware/include)
SRC=firmware/portrait36/src
COMMON=("$SRC/phone_http.cpp" "$SRC/phone_api.cpp" "$SRC/phone_setup_render.cpp" "$SRC/frame_session.cpp" "$SRC/epd_3in6e.cpp" firmware/src/portrait_frame.cpp)
g++ "${CXX[@]}" tools/portrait_driver/phone/test_phone.cpp "${COMMON[@]}" -o "$OUT/phone-protocol"
"$OUT/phone-protocol" | tee "$OUT/phone-protocol.json"
g++ "${CXX[@]}" -Itools/portrait_driver/phone/stubs tools/portrait_driver/phone/test_service.cpp "${COMMON[@]}" "$SRC/phone_service.cpp" "$SRC/phone_power.cpp" "$SRC/phone_power_policy.cpp" -o "$OUT/phone-service"
"$OUT/phone-service" | tee "$OUT/phone-service.json"
pio run -d firmware/portrait36 2>&1 | tee "$OUT/pio.log"
printf '%s
' 'PASS: host software suites and firmware compile; physical panel/WiFi/battery/RF NOT tested'
