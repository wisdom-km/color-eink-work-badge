#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""A provisional portrait badge, exact indexed pixels, and C++ rotation cross-check.

Dependencies: Pillow, reportlab; libzbar for independent QR decode verification.
The indices are a software palette, NOT a controller-ready frame or RF credential.
"""
import argparse
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import subprocess
import zlib

import PIL
import reportlab
from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.barcode import qrencoder

ROOT = Path(__file__).resolve().parents[2]
PALETTE = [(20, 24, 32), (255, 255, 255), (198, 35, 45), (244, 201, 38),
           (31, 78, 164), (28, 125, 75)]
PAYLOAD = "https://example.invalid/badge-demo"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pack(indices, bpp):
    result = bytearray((len(indices) * bpp + 7) // 8)
    for pixel, index in enumerate(indices):
        if not 0 <= index < 1 << bpp:
            raise ValueError("index does not fit pixel depth")
        result[pixel // (8 // bpp)] |= index << (8 - bpp - pixel % (8 // bpp) * bpp)
    return bytes(result)


def unpack(data, count, bpp):
    if len(data) != (count * bpp + 7) // 8:
        raise ValueError("frame size mismatch")
    return bytes((data[p // (8 // bpp)] >> (8 - bpp - p % (8 // bpp) * bpp)) & ((1 << bpp) - 1)
                 for p in range(count))


def colorize(indices, width, height, colors):
    rgb = b"".join(bytes(PALETTE[index]) for index in indices)
    if any(index >= colors for index in indices):
        raise ValueError("unknown palette index")
    return Image.frombytes("RGB", (width, height), rgb)


def decode_qr(image):
    """Use libzbar as an independent reader, rather than inspecting generator data."""
    path = ctypes.util.find_library("zbar")
    if not path:
        raise RuntimeError("libzbar is required for independent QR verification")
    lib = ctypes.CDLL(path)
    for name, restype, args in [
        ("zbar_image_scanner_create", ctypes.c_void_p, []),
        ("zbar_image_scanner_destroy", None, [ctypes.c_void_p]),
        ("zbar_image_scanner_set_config", ctypes.c_int, [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]),
        ("zbar_image_create", ctypes.c_void_p, []),
        ("zbar_image_destroy", None, [ctypes.c_void_p]),
        ("zbar_image_set_format", None, [ctypes.c_void_p, ctypes.c_ulong]),
        ("zbar_image_set_size", None, [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]),
        ("zbar_image_set_data", None, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]),
        ("zbar_scan_image", ctypes.c_int, [ctypes.c_void_p, ctypes.c_void_p]),
        ("zbar_image_first_symbol", ctypes.c_void_p, [ctypes.c_void_p]),
        ("zbar_symbol_get_data", ctypes.c_char_p, [ctypes.c_void_p]),
        ("zbar_symbol_next", ctypes.c_void_p, [ctypes.c_void_p]),
    ]:
        function = getattr(lib, name)
        function.restype = restype
        function.argtypes = args
    scanner, frame = lib.zbar_image_scanner_create(), lib.zbar_image_create()
    if not scanner or not frame:
        if frame:
            lib.zbar_image_destroy(frame)
        if scanner:
            lib.zbar_image_scanner_destroy(scanner)
        raise RuntimeError("zbar allocation failed")
    try:
        gray = image.convert("L")
        storage = ctypes.create_string_buffer(gray.tobytes())
        lib.zbar_image_scanner_set_config(scanner, 0, 0, 1)
        lib.zbar_image_set_format(frame, int.from_bytes(b"Y800", "little"))
        lib.zbar_image_set_size(frame, gray.width, gray.height)
        lib.zbar_image_set_data(frame, storage, len(gray.tobytes()), None)
        if lib.zbar_scan_image(scanner, frame) < 1:
            raise AssertionError("QR cannot be independently decoded")
        found = []
        symbol = lib.zbar_image_first_symbol(frame)
        while symbol:
            found.append(lib.zbar_symbol_get_data(symbol).decode("utf-8"))
            symbol = lib.zbar_symbol_next(symbol)
        return found
    finally:
        lib.zbar_image_destroy(frame)
        lib.zbar_image_scanner_destroy(scanner)


def draw_concept(width, height, colors, regular_path, bold_path):
    # Draw indexed primitives directly. Text masks are 1-bit, so no hidden gray,
    # dithering or antialiasing changes the six/four palette entries.
    canvas = Image.new("L", (width, height), 1)
    draw = ImageDraw.Draw(canvas)
    scale = min(width / 480, height / 720)
    offset_x, offset_y = (width - 480 * scale) / 2, (height - 720 * scale) / 2

    def point(x, y):
        return round(offset_x + x * scale), round(offset_y + y * scale)

    def rect(x, y, w, h, ink):
        left, top = point(x, y)
        right, bottom = point(x + w, y + h)
        draw.rectangle((left, top, right - 1, bottom - 1), fill=ink)

    def text(x, y, value, size, ink=0, bold=False):
        font = ImageFont.truetype(str(bold_path if bold else regular_path), max(1, round(size * scale)))
        mask = Image.new("1", (width, height), 0)
        painter = ImageDraw.Draw(mask)
        position = point(x, y)
        bounds = painter.textbbox(position, value, font=font, anchor="lt")
        if bounds[0] < 0 or bounds[1] < 0 or bounds[2] > width or bounds[3] > height:
            raise ValueError(f"text outside canvas: {value}")
        painter.text(position, value, font=font, fill=1, anchor="lt")
        canvas.paste(ink, (0, 0), mask)

    blue = 4 if colors == 6 else 0
    green = 5 if colors == 6 else 0
    rect(0, 0, 480, 12, blue)
    rect(32, 45, 56, 56, blue)
    # Deliberately abstract mark; no third-party company logo or invented identity.
    rect(44, 57, 12, 32, 1)
    rect(56, 77, 20, 12, 1)
    text(106, 43, "公司名称", 36, bold=True)
    text(107, 88, "COMPANY / DEMO", 15)
    rect(32, 128, 416, 2, 0)

    rect(32, 172, 6, 98, 2)
    text(55, 165, "姓名", 104, bold=True)
    text(56, 292, "YOUR NAME", 30, bold=True)
    rect(32, 356, 89, 28, 3)
    text(43, 360, "TEAM", 17, bold=True)
    text(32, 414, "职位 · 部门", 34, bold=True)
    text(34, 463, "ROLE / DEPARTMENT", 15)

    text(32, 539, "EMPLOYEE", 16)
    text(32, 571, "ID 0000", 31, bold=True)
    rect(32, 626, 8, 8, green)
    text(50, 622, "DEMO ONLY", 15)

    qr = qrencoder.QRCode(3, qrencoder.QRErrorCorrectLevel.M)
    qr.addData(PAYLOAD)
    qr.make()
    quiet = 4  # ISO-style four-module quiet zone, preserved after rasterization.
    modules = qr.moduleCount
    unit = max(1, int(148 * scale / (modules + quiet * 2)))
    extent = (modules + quiet * 2) * unit
    right, top = point(448, 507)
    left = right - extent
    if left < 0 or top + extent > height:
        raise ValueError("QR does not fit canvas")
    draw.rectangle((left, top, left + extent - 1, top + extent - 1), fill=1)
    for y in range(modules):
        for x in range(modules):
            if qr.isDark(y, x):
                px, py = left + (x + quiet) * unit, top + (y + quiet) * unit
                draw.rectangle((px, py, px + unit - 1, py + unit - 1), fill=0)
    # Explicit proof of the quiet zone, independent of the QR creator.
    for y in range(extent):
        for x in range(extent):
            if min(x, y, extent - 1 - x, extent - 1 - y) < quiet * unit:
                assert canvas.getpixel((left + x, top + y)) == 1
    rect(32, 675, 416, 2, 0)
    text(32, 691, "概念稿 / 非实屏", 14)
    text(300, 691, f"{width} x {height}", 14)
    return canvas.tobytes(), {"payload": PAYLOAD, "module_pixels": unit,
                              "quiet_zone_modules": quiet, "version": 3,
                              "error_correction": "M", "bounds": [left, top, extent, extent]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=400)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--colors", type=int, choices=[4, 6], default=6)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--regular-font", type=Path, default=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"))
    parser.add_argument("--bold-font", type=Path, default=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"))
    args = parser.parse_args()
    if not 240 <= args.width <= 2048 or not args.width < args.height <= 3072:
        parser.error("portrait dimensions must be 240 <= width <= 2048, width < height <= 3072")
    args.out.mkdir(parents=True, exist_ok=True)
    for font in [args.regular_font, args.bold_font]:
        if not font.is_file():
            parser.error(f"font missing: {font}; provide the corresponding --*-font")
    bpp = 4 if args.colors == 6 else 2
    indices, qr = draw_concept(args.width, args.height, args.colors, args.regular_font, args.bold_font)
    image = colorize(indices, args.width, args.height, args.colors)
    assert decode_qr(image) == [PAYLOAD]
    image.save(args.out / "portrait.png", optimize=False)
    image.resize((args.width * 2, args.height * 2), Image.Resampling.NEAREST).save(args.out / "portrait-2x.png", optimize=False)
    packed = pack(indices, bpp)
    assert unpack(packed, len(indices), bpp) == indices
    source = args.out / "portrait-indexed.bin"
    source.write_bytes(packed)
    executable = args.out / "frame-cli"
    subprocess.run([args.compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(ROOT / "firmware/include"), str(ROOT / "firmware/src/portrait_frame.cpp"),
                    str(Path(__file__).with_name("frame_cli.cpp")), "-o", str(executable)], check=True)
    rotated_file = args.out / "landscape-cw90-indexed.bin"
    subprocess.run([str(executable), str(args.width), str(args.height), str(bpp), "cw",
                    str(source), str(rotated_file)], check=True)
    rotated_indices = unpack(rotated_file.read_bytes(), len(indices), bpp)
    rotated = colorize(rotated_indices, args.height, args.width, args.colors)
    assert rotated.tobytes() == image.transpose(Image.Transpose.ROTATE_270).tobytes()
    assert decode_qr(rotated) == [PAYLOAD]
    rotated.save(args.out / "landscape-cw90.png", optimize=False)
    restored_file = args.out / "roundtrip-indexed.bin"
    subprocess.run([str(executable), str(args.height), str(args.width), str(bpp), "ccw",
                    str(rotated_file), str(restored_file)], check=True)
    assert restored_file.read_bytes() == packed
    # Convert semantic artwork indices to the actual sparse six-color controller
    # nibbles. Red/yellow MUST be swapped relative to this renderer's palette.
    native_manifest = None
    if (args.width, args.height, args.colors) == (400, 600, 6):
        semantic_to_controller = (0, 1, 3, 2, 5, 6)
        codes = bytes(semantic_to_controller[index] for index in indices)
        native = pack(codes, 4)
        assert len(native) == 120000
        restored_codes = unpack(native, len(codes), 4)
        controller_to_semantic = {code: index for index, code in enumerate(semantic_to_controller)}
        assert bytes(controller_to_semantic[code] for code in restored_codes) == indices
        (args.out / "panel-3in6e-native.bin").write_bytes(native)
        subprocess.run([str(executable), "--validate-3in6e", str(args.out / "panel-3in6e-native.bin"),
                        f"{zlib.crc32(native):08x}"], check=True)
        native_manifest = {"filename": "panel-3in6e-native.bin", "bytes": len(native),
                           "crc32_ieee": f"{zlib.crc32(native):08x}",
                           "sha256": sha(args.out / "panel-3in6e-native.bin"),
                           "codes": {"black": 0, "white": 1, "yellow": 2, "red": 3, "blue": 5, "green": 6},
                           "orientation": "400x600 native portrait; no rotation applied",
                           "cpp_frame_validation_and_crc": True, "hardware_verified": False}
    assets = ["portrait.png", "portrait-2x.png", "portrait-indexed.bin", "landscape-cw90.png",
              "landscape-cw90-indexed.bin", "roundtrip-indexed.bin"]
    manifest = {
        "status": "SOFTWARE PREVIEW; NOT A MEASURED PHYSICAL DISPLAY",
        "width": args.width, "height": args.height, "bits_per_pixel": bpp,
        "frame_bytes": len(packed), "palette_rgb": PALETTE[:args.colors],
        "packing": "MSB-first continuous row-major indexed pixels, no per-row padding",
        "controller_palette_mapping": ("3.6E codes: black=0, white=1, yellow=2, red=3, blue=5, green=6"
                                       if native_manifest else "UNASSIGNED for this concept specification"),
        "panel_measurement": False, "rf_credential": False, "native_panel_frame": native_manifest,
        "qr": {**qr, "independent_decoder": "libzbar", "portrait_and_rotated_decode": True},
        "fonts": {p.name: sha(p) for p in [args.regular_font, args.bold_font]},
        "python_dependencies": {"Pillow": PIL.__version__, "reportlab": reportlab.Version},
        "cpp_rotation_matches_independent_pillow_oracle": True,
        "cpp_roundtrip_identical": True,
        "sha256": {name: sha(args.out / name) for name in assets},
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
