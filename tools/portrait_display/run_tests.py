#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile isolated framebuffer/CRC host tests with ASan and UBSan."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    # This managed environment uses ptrace; LeakSanitizer is unsupported there.
    # Address/undefined behavior sanitizers remain enabled with fatal errors.
    environment["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1"
    environment["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    reports = {}
    for name in ["test_frame", "test_transaction"]:
        executable = args.out / name
        command = [args.compiler, "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                   "-Wconversion", "-Wsign-conversion", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                   "-I" + str(ROOT / "firmware/include"), str(ROOT / "firmware/src/portrait_frame.cpp"),
                   str(Path(__file__).with_name(name + ".cpp")), "-o", str(executable)]
        build = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (args.out / (name + "-build.log")).write_text(build.stdout, encoding="utf-8")
        build.check_returncode()
        run = subprocess.run([str(executable)], env=environment, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (args.out / (name + "-stderr.log")).write_text(run.stderr, encoding="utf-8")
        run.check_returncode()
        reports[name] = json.loads(run.stdout)
        assert reports[name]["passed"]
    reports["toolchain"] = subprocess.check_output([args.compiler, "--version"], text=True).splitlines()[0]
    reports["sanitizers"] = {"address": True, "undefined_behavior": True,
                             "leak": False, "leak_limit": "LeakSanitizer is incompatible with ptrace in this environment"}
    reports["production_hardware_pass"] = False
    (args.out / "tests.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
