"""Generate the NFC spiral antenna as a KiCad net-tie footprint (lib/badge.pretty/NFC_Loop.kicad_mod).

The coil is copper graphics inside the footprint so DRC accepts it (net_tie_pad_groups),
Freerouting leaves it alone, and the whole antenna moves as one object.
Geometry comes from design.py (NFC_COIL_RECT / NFC_TURNS / trace width & gap).
The footprint is authored MIRRORED in X because every part on this board is flipped
to the back side; after the flip the coil lands exactly on design.NFC_COIL_RECT.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "lib", "badge.pretty", "NFC_Loop.kicad_mod")


def coil_points():
    x0, y0, x1, y1 = D.NFC_COIL_RECT
    p = D.NFC_TRACE_W + D.NFC_TRACE_GAP
    pts = [(x1, y1)]
    L, T, R, B = x0, y0, x1, y1
    for _ in range(D.NFC_TURNS):
        pts.append((R, T))
        pts.append((L, T))
        B2 = B - p
        pts.append((L, B2))
        R2 = R - p
        pts.append((R2, B2))
        L, T, R, B = L + p, T + p, R2, B2
    return pts


def inductance_uH():
    x0, y0, x1, y1 = D.NFC_COIL_RECT
    n = D.NFC_TURNS
    p = D.NFC_TRACE_W + D.NFC_TRACE_GAP
    d_out = math.sqrt((x1 - x0) * (y1 - y0))
    d_in = d_out - 2 * n * p
    d_avg = (d_out + d_in) / 2 / 1000
    rho = (d_out - d_in) / (d_out + d_in)
    return 2.34 * 4e-7 * math.pi * n * n * d_avg / (1 + 2.75 * rho) * 1e6, d_in


def center():
    x0, y0, x1, y1 = D.NFC_COIL_RECT
    return (x0 + x1) / 2, (y0 + y1) / 2


def feed_positions():
    """Board-frame positions of pad 1 (outer end) and pad 2 (bridge landing)."""
    x0, y0, x1, y1 = D.NFC_COIL_RECT
    pts = coil_points()
    xi, yi = pts[-1]
    fy = y1 + 1.6
    return (x1, fy), (xi, fy), (xi, yi)


def main():
    cx, cy = center()
    pts = coil_points()
    (p1x, p1y), (p2x, p2y), (xi, yi) = feed_positions()
    w = D.NFC_TRACE_W
    L, d_in = inductance_uH()
    f0 = 1 / (2 * math.pi * math.sqrt(L * 1e-6 * 28.5e-12)) / 1e6

    def loc(x, y):
        # footprint-local, mirrored in X (see module docstring)
        return f"{-(x - cx):.3f} {(y - cy):.3f}"

    lines = []
    lines.append('(footprint "NFC_Loop"')
    lines.append('\t(version 20240108)')
    lines.append('\t(generator "badge_gen")')
    lines.append('\t(generator_version "9.0")')
    lines.append('\t(layer "F.Cu")')
    x0, y0, x1, y1 = D.NFC_COIL_RECT
    lines.append(f'\t(descr "13.56 MHz PCB spiral antenna, {D.NFC_TURNS} turns, {x1-x0:.0f}x{y1-y0:.0f} mm, {w} mm trace / {D.NFC_TRACE_GAP} mm gap, L ~ {L:.1f} uH (modified Wheeler). The spiral is a custom-shaped pad 1; pad 2 is the inner end brought out through a through-hole bridge on the other layer. Net-tie footprint.")')
    lines.append('\t(tags "nfc antenna coil 13.56MHz ST25DV")')
    lines.append('\t(attr smd exclude_from_pos_files exclude_from_bom)')
    lines.append('\t(net_tie_pad_groups "1,2")')
    lines.append(f'\t(property "Reference" "ANT1" (at {loc(cx, y1 + 3.2)} 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))')
    lines.append(f'\t(property "Value" "NFC_Loop" (at {loc(cx, cy)} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
    # courtyard / fab
    m = 1.0
    lines.append(f'\t(fp_rect (start {loc(x0 - m, y0 - m)}) (end {loc(x1 + m, y1 + 2.6)}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))')
    lines.append(f'\t(fp_rect (start {loc(x0, y0)}) (end {loc(x1, y1)}) (stroke (width 0.12) (type default)) (fill none) (layer "F.Fab"))')
    # pad 1: custom shape = anchor at the feed point + the whole spiral as line primitives
    def rel(x, y):
        return f"{-(x - p1x):.3f} {(y - p1y):.3f}"
    prims = [f'\t\t\t(gr_line (start {rel(p1x, p1y)}) (end {rel(x1, y1)}) (width {w}))']
    # stop the spiral 0.7 mm before the inner through-hole so the hole keeps its 0.25 mm
    # clearance; the 1.1 mm annular ring of pad 2 overlaps the line end by ~0.1 mm
    segs = list(zip(pts, pts[1:]))
    (lx, ly), (ex, ey) = segs[-1]
    segs[-1] = ((lx, ly), (ex - 0.7, ey))
    for (ax, ay), (bx, by) in segs:
        prims.append(f'\t\t\t(gr_line (start {rel(ax, ay)}) (end {rel(bx, by)}) (width {w}))')
    lines.append(f'\t(pad "1" smd custom (at {loc(p1x, p1y)}) (size 1.0 1.0) (layers "F.Cu")')
    lines.append('\t\t(options (clearance outline) (anchor rect))')
    lines.append('\t\t(primitives')
    lines.extend(prims)
    lines.append('\t\t)')
    lines.append('\t)')
    # pad 2: through-hole at the inner end (its annular ring overlaps the end of pad 1),
    # a custom pad on the OTHER copper layer forming the bridge, and a through-hole landing
    # outside the coil that the router connects to. Same pad number -> one net, and KiCad
    # connectivity sees pad copper (footprint graphics would not count).
    lines.append(f'\t(pad "2" thru_hole circle (at {loc(xi, yi)}) (size 1.1 1.1) (drill 0.3) (layers "*.Cu" "*.Mask") (remove_unused_layers no))')
    lines.append(f'\t(pad "2" thru_hole circle (at {loc(p2x, p2y)}) (size 0.9 0.9) (drill 0.3) (layers "*.Cu" "*.Mask") (remove_unused_layers no))')
    def rel2(x, y):
        return f"{-(x - p2x):.3f} {(y - p2y):.3f}"
    lines.append(f'\t(pad "2" smd custom (at {loc(p2x, p2y)}) (size 0.9 0.9) (layers "B.Cu")')
    lines.append('\t\t(options (clearance outline) (anchor circle))')
    lines.append('\t\t(primitives')
    lines.append(f'\t\t\t(gr_line (start {rel2(p2x, p2y)}) (end {rel2(xi, yi)}) (width {w}))')
    lines.append('\t\t)')
    lines.append('\t)')
    lines.append(')')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")
    print(f"coil: {D.NFC_TURNS} turns {x1-x0:.0f}x{y1-y0:.0f} mm, eq. inner {d_in:.1f} mm, L ~ {L:.2f} uH, "
          f"f0 ~ {f0:.2f} MHz with 28.5 pF (target 13.56)")
    print(f"feed pads (board frame): pad1 {p1x:.1f},{p1y:.1f}  pad2 {p2x:.1f},{p2y:.1f}")


if __name__ == "__main__":
    main()
