#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./build_driver.sh
binary=$(mktemp /tmp/g13-profile-tests-XXXXXX)
trap 'rm -f "$binary"' EXIT
g++ -Isrc/cpp -Iusr/include tests/test_profiles.cpp src/cpp/{G13,G13Action,Macro,MacroAction,Output,PassThroughAction,G13LogiFrame}.o -Lusr/lib/x86_64-linux-gnu -lusb-1.0 -ludev -pthread -Wl,--wrap=libusb_open -Wl,--wrap=libusb_control_transfer -Wl,--wrap=libusb_interrupt_transfer -o "$binary"
"$binary"
