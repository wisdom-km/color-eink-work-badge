"""Split design.py into engineering vs SMT-assembly lists. Does not change copper.

Engineering BOM keeps ANT1, test pads, and C11 (DNP). Assembly BOM / position
files drop those. C11 is DNP for first article until NFC resonance is measured.
KiCad grouped BOM historically omitted C11 entirely; this script reads
design.py so DNP parts cannot disappear.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design as D

HERE = Path(__file__).resolve().parent
PCB_DIR = HERE.parent
OUT = PCB_DIR / "output"

ENG_FIELDS = ["Ref", "Value", "Footprint", "Description", "LCSC", "Qty", "DNP", "Class", "Assemble"]
ASM_FIELDS = ["Ref", "Value", "Footprint", "Description", "LCSC", "Qty"]


def part_class(part):
    if part.ref == "ANT1":
        return "pcb_feature"
    if part.ref.startswith("TP"):
        return "testpoint"
    if part.dnp:
        return "dnp"
    return "smt"


def assemble(part):
    return part_class(part) == "smt"


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def filter_pos(src, dst, keep_refs):
    lines = Path(src).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit("empty position file: %s" % src)
    header, body = lines[0], lines[1:]
    kept = [header]
    dropped = []
    for line in body:
        if not line.strip():
            continue
        ref = line.split(",", 1)[0].strip().strip('"')
        if ref in keep_refs:
            kept.append(line)
        else:
            dropped.append(ref)
    Path(dst).write_text("\n".join(kept) + "\n", encoding="utf-8")
    return dropped


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default=str(OUT))
    p.add_argument("--pos", default="")
    args = p.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    parts = sorted(D.PARTS, key=lambda x: x.ref)
    eng_rows, asm_rows = [], []
    for part in parts:
        cls = part_class(part)
        row = {
            "Ref": part.ref,
            "Value": part.value,
            "Footprint": part.footprint,
            "Description": part.desc,
            "LCSC": part.lcsc,
            "Qty": "1",
            "DNP": "Y" if part.dnp else "",
            "Class": cls,
            "Assemble": "Y" if assemble(part) else "N",
        }
        eng_rows.append(row)
        if assemble(part):
            asm_rows.append({k: row[k] for k in ASM_FIELDS})

    write_csv(out / "badge_bom_engineering.csv", ENG_FIELDS, eng_rows)
    write_csv(out / "badge_bom_assembly.csv", ASM_FIELDS, asm_rows)

    notes = out / "bom_classes.txt"
    notes.write_text(
        "\n".join([
            "C11: DNP on first article. Do not SMT. Fit only after measuring antenna resonance;",
            "ST25DV has 28.5 pF internal. Record populated value in the tune log (F14).",
            "ANT1: PCB copper loop, not a pick-and-place part. Keep on engineering BOM.",
            "TP1-TP4: test pads, not SMT. Keep on engineering BOM, drop from assembly POS.",
            "U3 charger is TP4054 (C32574). Battery 202545 250mAh 2.0mm with PCM; J2-1=VBAT.",
            "KiCad grouped BOM (badge_bom.csv) may omit DNP; engineering CSV is the complete set from design.py.",
            "",
        ]),
        encoding="utf-8",
    )

    keep = {part.ref for part in parts if assemble(part)}
    pos_src = Path(args.pos) if args.pos else (OUT / "badge_pos_back.csv")
    dropped = []
    if pos_src.is_file():
        dropped = filter_pos(pos_src, out / "badge_pos_back_assembly.csv", keep)
        asm_refs = {r["Ref"] for r in asm_rows}
        pos_refs = set()
        for line in Path(out / "badge_pos_back_assembly.csv").read_text(encoding="utf-8").splitlines()[1:]:
            if line.strip():
                pos_refs.add(line.split(",", 1)[0].strip().strip('"'))
        if pos_refs != asm_refs:
            print("assembly BOM refs %s vs position refs %s" % (sorted(asm_refs ^ pos_refs), ""), file=sys.stderr)
            raise SystemExit(1)

    print("engineering", len(eng_rows), "assembly", len(asm_rows), "pos_dropped", dropped)


if __name__ == "__main__":
    main()
