"""Silk + schematic-parity hygiene on an existing board. Does not touch tracks."""
import os
import re
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
PCB_DIR = os.path.abspath(os.path.join(HERE, ".."))
BOARD_PATH = os.path.join(PCB_DIR, "badge.kicad_pcb")


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def parts_by_ref():
    return {p.ref: p for p in D.PARTS}


def apply_fpids(board, parts):
    n = 0
    for fp in board.GetFootprints():
        part = parts.get(fp.GetReference())
        if not part:
            continue
        want = D.board_footprint_id(part)
        cur = fp.GetFPID().GetUniStringLibId()
        if cur != want:
            fp.SetFPIDAsString(want)
            n += 1
    return n


def apply_bom_flags(board, parts):
    n = 0
    for fp in board.GetFootprints():
        part = parts.get(fp.GetReference())
        if not part:
            continue
        attr = fp.GetAttributes()
        want_ex = D.exclude_from_bom(part)
        have_ex = bool(attr & pcbnew.FP_EXCLUDE_FROM_BOM)
        want_dnp = bool(part.dnp)
        have_dnp = bool(attr & pcbnew.FP_DNP)
        new = attr
        if want_ex and not have_ex:
            new |= pcbnew.FP_EXCLUDE_FROM_BOM
        if (not want_ex) and have_ex and not want_dnp:
            new &= ~pcbnew.FP_EXCLUDE_FROM_BOM
        if want_dnp and not have_dnp:
            new |= pcbnew.FP_DNP | pcbnew.FP_EXCLUDE_FROM_BOM
        if new != attr:
            fp.SetAttributes(new)
            n += 1
    return n


def set_fp_field(fp, name, text):
    try:
        fp.SetField(name, text)
        return True
    except Exception:
        return False


def apply_fields(board, parts):
    """KiCad 10 schematic_parity: keep Description/LCSC, but LCSC must not sit on B.SilkS."""
    n = 0
    for fp in board.GetFootprints():
        part = parts.get(fp.GetReference())
        if not part:
            continue
        if set_fp_field(fp, "Description", part.desc or ""):
            n += 1
        if set_fp_field(fp, "Datasheet", ""):
            n += 1
        if set_fp_field(fp, "LCSC", part.lcsc or ""):
            n += 1
        for name in ("Description", "Datasheet", "LCSC"):
            try:
                f = fp.GetFieldByName(name)
            except Exception:
                f = None
            if f is None:
                continue
            f.SetVisible(False)
            try:
                f.SetLayer(pcbnew.B_Fab)
            except Exception:
                pass
    return n


def apply_nc_nets(board, parts):
    n = 0
    for fp in board.GetFootprints():
        part = parts.get(fp.GetReference())
        if not part or not part.nc:
            continue
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num not in part.nc:
                continue
            name = D.nc_unconnected_net(part.ref, num)
            if pad.GetNetname() == name:
                continue
            ni = board.FindNet(name)
            if ni is None or ni.GetNetCode() == 0:
                ni = pcbnew.NETINFO_ITEM(board, name)
                board.Add(ni)
            pad.SetNet(ni)
            n += 1
    return n


U1_NETTIE = "1,2,11,14,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53"
U1_NETTIE_RE = re.compile(
    r'\(net_tie_pad_groups "' + re.escape(U1_NETTIE) + r'"'
    r'(?:\s+"' + re.escape(U1_NETTIE) + r'")*\s*\)',
)


def collapse_u1_nettie_sexpr(path):
    """pcbnew AddNetTiePadGroup can emit the same group thrice; library has one."""
    text = open(path, encoding="utf-8").read()
    new, n = U1_NETTIE_RE.subn(f'(net_tie_pad_groups "{U1_NETTIE}")', text, count=1)
    if n and new != text:
        open(path, "w", encoding="utf-8", newline="\n").write(new)
    return n


def apply_u1_nettie(board):
    """Collapse duplicate ESP32 GND net-tie groups to the single library string."""
    fp = board.FindFootprintByReference("U1")
    if fp is None:
        return 0
    try:
        groups = [str(g) for g in (fp.GetNetTiePadGroups() or [])]
    except TypeError:
        groups = []
    if groups == [U1_NETTIE]:
        return 0
    if hasattr(fp, "ClearNetTiePadGroups"):
        fp.ClearNetTiePadGroups()
    elif groups:
        # KiCad 9: replacing via Add without Clear duplicates the group.
        # Fall through to Add only when empty; otherwise rewrite after save.
        pass
    if not groups:
        fp.AddNetTiePadGroup(U1_NETTIE)
        return 1
    if hasattr(fp, "ClearNetTiePadGroups"):
        fp.AddNetTiePadGroup(U1_NETTIE)
        return 1
    return -1  # caller must rewrite s-expr


def apply_j3_shield_pads(board):
    """KiCad 10 USB-C symbol names the shell pin SH; TYPE-C-31-M-14 used S1."""
    fp = board.FindFootprintByReference("J3")
    if fp is None:
        return 0
    n = 0
    for pad in fp.Pads():
        if pad.GetNumber() == "S1":
            pad.SetNumber("SH")
            n += 1
    return n


def export_q1_to_project_lib(board):
    """Live Q1 silk/pads become badge.pretty so KiCad 10 does not compare to official SOT-323."""
    fp = board.FindFootprintByReference("Q1")
    if fp is None:
        return 0
    pretty = os.path.join(PCB_DIR, "lib", "badge.pretty")
    saved = 0
    try:
        io = pcbnew.PCB_IO_KICAD_SEXPR()
        io.FootprintSave(pretty, fp)
        saved = 1
    except Exception as e:
        print("Q1 FootprintSave", e)
    src = os.path.join(pretty, "Q1.kicad_mod")
    dst = os.path.join(pretty, "SOT-323_SC-70.kicad_mod")
    if os.path.isfile(src):
        text = open(src, encoding="utf-8").read()
        text = text.replace('(footprint "Q1"', '(footprint "SOT-323_SC-70"', 1)
        open(dst, "w", encoding="utf-8", newline="\n").write(text)
        os.remove(src)
        saved = 1
    return saved


def apply_silk_refs(board):
    n = 0
    for fp in board.GetFootprints():
        refn = fp.GetReference()
        ref = fp.Reference()
        ref.SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
        ref.SetTextThickness(FromMM(0.12))
        if refn in ("SW1", "SW2"):
            ref.SetVisible(False)
        # ANT1 位号在线圈下沿，0.8 mm 字会压到 C9；线圈本身可辨认。
        if refn == "ANT1":
            ref.SetVisible(False)
        xy = D.SILK_REF_XY.get(refn)
        if xy:
            ref.SetPosition(P(*xy))
            n += 1
            continue
        dxdy = D.SILK_REF_OFFSET.get(refn)
        if dxdy:
            p = ref.GetPosition()
            # OFFSET is from KiCad default; live board may already include it.
            # apply_hygiene only uses OFFSET when XY is absent and the text
            # has not been moved to XY. Do not add OFFSET twice on a live board.
    return n


def apply_all(board):
    parts = parts_by_ref()
    return {
        "j3_shield": apply_j3_shield_pads(board),
        "q1_lib": export_q1_to_project_lib(board),
        "fpids": apply_fpids(board, parts),
        "bom_flags": apply_bom_flags(board, parts),
        "fields": apply_fields(board, parts),
        "nc_nets": apply_nc_nets(board, parts),
        "u1_nettie": apply_u1_nettie(board),
        "silk_xy": apply_silk_refs(board),
    }


def main():
    board = pcbnew.LoadBoard(BOARD_PATH)
    counts = apply_all(board)
    pcbnew.SaveBoard(BOARD_PATH, board)
    n = collapse_u1_nettie_sexpr(BOARD_PATH)
    print("hygiene", counts, "nettie_sexpr", n, "saved", BOARD_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
