"""Generate hardware/pcb/badge.kicad_sch from design.py.

Layout strategy: every symbol gets a global label on each connected pin (netlist-style
schematic grouped by functional section). Unconnected pins get no-connect markers.
"""
import os
import sys
import uuid
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
import design as D
import kicad_sym as K

HERE = os.path.dirname(os.path.abspath(__file__))
PCB_DIR = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(PCB_DIR, "badge.kicad_sch")

ROOT_UUID = "0f1a3f2e-badc-4e00-9a11-000000000001"   # stable so instances survive regeneration
PROJECT = "badge"

SYM_LIBS = {
    "Device": f"{D.KICAD_SYM}/Device.kicad_sym",
    "Connector": f"{D.KICAD_SYM}/Connector.kicad_sym",
    "Connector_Generic": f"{D.KICAD_SYM}/Connector_Generic.kicad_sym",
    "Battery_Management": f"{D.KICAD_SYM}/Battery_Management.kicad_sym",
    "Regulator_Linear": f"{D.KICAD_SYM}/Regulator_Linear.kicad_sym",
    "Transistor_FET": f"{D.KICAD_SYM}/Transistor_FET.kicad_sym",
    "Diode": f"{D.KICAD_SYM}/Diode.kicad_sym",
    "Switch": f"{D.KICAD_SYM}/Switch.kicad_sym",
    "RF_NFC": f"{D.KICAD_SYM}/RF_NFC.kicad_sym",
    "power": f"{D.KICAD_SYM}/power.kicad_sym",
    "Espressif": os.path.join(PCB_DIR, D.ESPRESSIF_SYM),
    "Badge": os.path.join(PCB_DIR, "lib", "badge.kicad_sym"),
}

GRID = 1.27
STRIP_V10 = "10.0" not in D.KICAD_SYM.replace("\\", "/")


def snap(v):
    return round(round(v / GRID) * GRID, 2)


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def label_rot(pin_angle):
    return int((pin_angle + 180) % 360)


class Sheet:
    def __init__(self):
        self.lib_symbols = {}
        self.items = []

    def add_lib_symbol(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.lib_symbols:
            tree = K.lib_tree(SYM_LIBS[lib])
            self.lib_symbols[key] = K.resolve_symbol(tree, name, key, strip_v10=STRIP_V10)
        return self.lib_symbols[key]

    def place_symbol(self, part, x, y, sym_def):
        pins = K.symbol_pins(sym_def)
        pxs = [p["x"] for p in pins] or [0]
        pys = [p["y"] for p in pins] or [0]
        top = y - max(pys) - 2.54
        bottom = y - min(pys) + 2.54
        s = []
        s.append(f'  (symbol (lib_id {q(f"{part.lib}:{part.symbol}")}) (at {x} {y} 0) (unit 1)')
        s.append(f'    (exclude_from_sim no) (in_bom {"no" if D.exclude_from_bom(part) else "yes"}) (on_board yes) (dnp {"yes" if part.dnp else "no"})')
        s.append(f'    (uuid {q(uuid.uuid4())})')
        s.append(f'    (property "Reference" {q(part.ref)} (at {x} {snap(top)} 0) (effects (font (size 1.27 1.27))))')
        s.append(f'    (property "Value" {q(part.value)} (at {x} {snap(bottom)} 0) (effects (font (size 1.27 1.27))))')
        s.append(f'    (property "Footprint" {q(D.board_footprint_id(part))} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        s.append(f'    (property "Datasheet" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        s.append(f'    (property "Description" {q(part.desc)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        s.append(f'    (property "LCSC" {q(part.lcsc)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        for p in pins:
            if p["number"] in part.omit_pins:
                continue
            s.append(f'    (pin {q(p["number"])} (uuid {q(uuid.uuid4())}))')
        s.append(f'    (instances (project {q(PROJECT)} (path {q("/" + ROOT_UUID)} (reference {q(part.ref)}) (unit 1))))')
        s.append('  )')
        self.items.append("\n".join(s))

        # labels / no-connects at pin ends
        seen_pos = set()
        for p in pins:
            if p["number"] in part.omit_pins:
                continue
            px, py = snap(x + p["x"]), snap(y - p["y"])
            net = part.pins.get(p["number"])
            if net:
                if (px, py) in seen_pos:
                    continue
                seen_pos.add((px, py))
                self.global_label(net, px, py, label_rot(p["angle"]))
            elif p["number"] in part.nc or p["type"] != "no_connect":
                if (px, py) in seen_pos:
                    continue
                seen_pos.add((px, py))
                self.items.append(f'  (no_connect (at {px} {py}) (uuid {q(uuid.uuid4())}))')
        return (min(pxs), max(pxs), min(pys), max(pys))

    def global_label(self, net, x, y, rot):
        justify = "left" if rot in (0, 90) else "right"
        self.items.append(
            f'  (global_label {q(net)} (shape input) (at {x} {y} {rot}) (fields_autoplaced yes)\n'
            f'    (effects (font (size 1.27 1.27)) (justify {justify}))\n'
            f'    (uuid {q(uuid.uuid4())})\n'
            f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'  )')

    def text(self, txt, x, y, size=2.0):
        self.items.append(
            f'  (text {q(txt)} (exclude_from_sim no) (at {x} {y} 0)\n'
            f'    (effects (font (size {size} {size}) (bold yes)) (justify left bottom))\n'
            f'    (uuid {q(uuid.uuid4())})\n  )')

    def rect(self, x1, y1, x2, y2):
        self.items.append(
            f'  (rectangle (start {x1} {y1}) (end {x2} {y2})\n'
            f'    (stroke (width 0.3) (type dash)) (fill (type none))\n    (uuid {q(uuid.uuid4())})\n  )')


def symbol_extent(sym_def):
    pins = K.symbol_pins(sym_def)
    pxs = [abs(p["x"]) for p in pins] or [5]
    pys = [abs(p["y"]) for p in pins] or [5]
    # room for a ~14 char label on each side
    return max(pxs) + 22.0, max(pys) + 7.0


def main():
    sh = Sheet()
    sections = ["USB", "POWER", "MCU", "NFC", "EPD"]
    sheet_w = 820.0
    margin_x = 12.0
    y_cursor = 20.0

    for sec in sections:
        parts = [p for p in D.PARTS if p.section == sec]
        sh.text(f"{sec}  -  {D.SECTION_NOTES.get(sec, '')}", margin_x, y_cursor, size=2.0)
        y_cursor += 6.0
        x_cursor = margin_x
        row_h = 0.0
        row_top = y_cursor
        sec_top = y_cursor - 8
        for part in parts:
            sym_def = sh.add_lib_symbol(part.lib, part.symbol)
            hw, hh = symbol_extent(sym_def)
            w, h = 2 * hw, 2 * hh + 8
            if x_cursor + w > sheet_w - margin_x:
                x_cursor = margin_x
                row_top += row_h
                row_h = 0.0
            cx, cy = snap(x_cursor + hw), snap(row_top + hh + 4)
            sh.place_symbol(part, cx, cy, sym_def)
            x_cursor += w
            row_h = max(row_h, h)
        y_cursor = row_top + row_h + 6
        sh.rect(margin_x - 4, sec_top, sheet_w - margin_x + 4, y_cursor - 2)
        y_cursor += 10

    # PWR_FLAGs
    sh.text("ERC power flags", margin_x, y_cursor, size=2.0)
    y_cursor += 8
    flag_def = sh.add_lib_symbol("power", "PWR_FLAG")
    fp = K.symbol_pins(flag_def)[0]
    for i, net in enumerate(D.PWR_FLAG_NETS):
        cx, cy = snap(margin_x + 30 + i * 40), snap(y_cursor + 8)
        part = D.Part(f"#FLG0{i+1}", "power", "PWR_FLAG", "", "PWR_FLAG", {"1": net})
        sh.place_symbol(part, cx, cy, flag_def)
    y_cursor += 24

    paper = "A1"
    out = []
    out.append(f'(kicad_sch (version 20250114) (generator "badge_gen") (generator_version {"10.0" if not STRIP_V10 else "9.0"})')
    out.append(f'  (uuid {q(ROOT_UUID)})')
    out.append(f'  (paper {q(paper)})')
    out.append('  (title_block')
    out.append('    (title "4.2\\" BWRY e-paper NFC badge")')
    out.append(f'    (date {q(date.today().isoformat())})')
    out.append('    (rev "v0.1")')
    out.append('    (comment 1 "Generated by hardware/pcb/scripts/gen_schematic.py - do not edit by hand")')
    out.append('  )')
    out.append('  (lib_symbols')
    for key, sym in sh.lib_symbols.items():
        out.append("    " + K.dumps(sym))
    out.append('  )')
    out.extend(sh.items)
    out.append('  (sheet_instances (path "/" (page "1")))')
    out.append(')')
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"wrote {OUT}: {len(D.PARTS)} symbols, sheet height used {y_cursor:.0f} mm")


if __name__ == "__main__":
    main()
