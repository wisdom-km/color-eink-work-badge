"""Generate hardware/pcb/badge.kicad_pcb from design.py using the pcbnew Python API.

Steps: board setup -> nets -> footprints (all on B.Cu) -> outline/slot -> NFC spiral
antenna note -> rule areas -> GND pours -> zone fill. Routing lives in route_pcb.py.
Run:  python3 gen_pcb.py   (then route_pcb.py for autorouting + GND stitching)
"""
import math
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM

sys.path.insert(0, os.path.dirname(__file__))
import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
PCB_DIR = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(PCB_DIR, "badge.kicad_pcb")
OUT_DIR = os.path.join(PCB_DIR, "output")


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def fp_lib_path(nick):
    if nick == "badge":
        return os.path.join(PCB_DIR, D.PROJECT_FP, "badge.pretty")
    return os.path.join(D.KICAD_FP, nick + ".pretty")


class Gen:
    def __init__(self):
        self.board = pcbnew.BOARD()
        self.nets = {}
        self.fps = {}
        ds = self.board.GetDesignSettings()
        ds.SetBoardThickness(FromMM(D.BOARD_THICKNESS))
        ds.m_CopperEdgeClearance = FromMM(0.1)   # mid-mount USB-C shell stakes sit right beside the cutout
        ds.m_MinClearance = FromMM(0.15)
        ds.m_TrackMinWidth = FromMM(0.15)
        ds.m_ViasMinSize = FromMM(0.4)
        ds.m_MinThroughDrill = FromMM(0.2)  # 0.4/0.2 stitching vias; 4:1 aspect on 0.8 mm board
        ds.m_HoleClearance = FromMM(0.25)

    def apply_net_classes(self):
        """Write design.py NET_CLASSES into the board and badge.kicad_pro (F05)."""
        ns = self.board.GetDesignSettings().m_NetSettings
        for name, spec in D.NET_CLASSES.items():
            if name == "Default":
                nc = ns.GetDefaultNetclass()
            elif ns.HasNetclass(name):
                nc = ns.GetNetClassByName(name)
            else:
                nc = pcbnew.NETCLASS(name)
            nc.SetTrackWidth(FromMM(spec["track"]))
            nc.SetClearance(FromMM(spec["clearance"]))
            nc.SetViaDiameter(FromMM(spec["via"]))
            nc.SetViaDrill(FromMM(spec["via_drill"]))
            if name != "Default":
                ns.SetNetclass(name, nc)
            for netname in spec["nets"]:
                ns.SetNetclassPatternAssignment(netname, name)
        self.write_project_netclasses()

    def write_project_netclasses(self):
        import json
        pro = os.path.join(PCB_DIR, "badge.kicad_pro")
        data = json.loads(open(pro, encoding="utf-8").read())
        classes = []
        for name, spec in D.NET_CLASSES.items():
            classes.append({
                "bus_width": 12,
                "clearance": spec["clearance"],
                "diff_pair_gap": 0.25,
                "diff_pair_via_gap": 0.25,
                "diff_pair_width": 0.2,
                "line_style": 0,
                "microvia_diameter": 0.3,
                "microvia_drill": 0.1,
                "name": name,
                "pcb_color": "rgba(0, 0, 0, 0.000)",
                "priority": 2147483647 if name == "Default" else 0,
                "schematic_color": "rgba(0, 0, 0, 0.000)",
                "track_width": spec["track"],
                "via_diameter": spec["via"],
                "via_drill": spec["via_drill"],
                "wire_width": 6,
            })
        patterns = []
        for name, spec in D.NET_CLASSES.items():
            for netname in spec["nets"]:
                patterns.append({"netclass": name, "pattern": netname})
        data["net_settings"]["classes"] = classes
        data["net_settings"]["netclass_patterns"] = patterns
        with open(pro, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    # ------------------------------------------------------------------ nets
    def net(self, name):
        if name not in self.nets:
            ni = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(ni)
            self.nets[name] = ni
        return self.nets[name]

    # ------------------------------------------------------------ footprints
    def place_parts(self):
        overflow_x = 2.0
        for part in D.PARTS:
            lib, name = part.footprint.split(":")
            fp = pcbnew.FootprintLoad(fp_lib_path(lib), name)
            if fp is None:
                raise RuntimeError(f"footprint not found: {part.footprint}")
            fp.SetReference(part.ref)
            fp.SetValue(part.value)
            self.board.Add(fp)
            fp.SetFPIDAsString(D.board_footprint_id(part))
            if part.at is None:
                x, y, rot = overflow_x, -8.0, 0
                overflow_x += 6
            else:
                x, y, rot = part.at
            fp.SetPosition(P(x, y))
            # Everything lives on the back. KiCad implements a left/right flip as "mirror Y +
            # rotate 180", so the footprint ends up with orientation 180; add the requested
            # rotation on top instead of overwriting it (overwriting would turn the flip into a
            # top/bottom mirror).
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            fp.SetOrientationDegrees(fp.GetOrientationDegrees() + rot)
            if D.exclude_from_bom(part):
                fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM)
            if part.dnp:
                fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_DNP | pcbnew.FP_EXCLUDE_FROM_BOM)
            for pad in fp.Pads():
                net = part.pins.get(pad.GetNumber())
                if net:
                    pad.SetNet(self.net(net))
                elif pad.GetNumber() in part.nc:
                    pad.SetNet(self.net(D.nc_unconnected_net(part.ref, pad.GetNumber())))
            # keep reference text at DRC silk min 0.8 mm
            ref = fp.Reference()
            ref.SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
            ref.SetTextThickness(FromMM(0.12))
            xy = D.SILK_REF_XY.get(part.ref)
            if xy:
                ref.SetPosition(P(*xy))
            else:
                dxdy = D.SILK_REF_OFFSET.get(part.ref)
                if dxdy:
                    p = ref.GetPosition()
                    ref.SetPosition(VECTOR2I(p.x + FromMM(dxdy[0]), p.y + FromMM(dxdy[1])))
            # SW1/SW2 refs land on the BOOT/RST labels; hide them.
            # ANT1 coil is obvious; its 0.8 mm ref sits on C9's pocket.
            if part.ref in ("SW1", "SW2", "ANT1"):
                ref.SetVisible(False)
            fp.Value().SetVisible(False)
            try:
                fp.SetField("Description", part.desc or "")
                fp.SetField("Datasheet", "")
                fp.SetField("LCSC", part.lcsc or "")
                for name in ("Description", "Datasheet", "LCSC"):
                    f = fp.GetFieldByName(name)
                    if f:
                        f.SetVisible(False)
                        try:
                            f.SetLayer(pcbnew.B_Fab)
                        except Exception:
                            pass
            except Exception:
                pass
            self.fps[part.ref] = fp

    # --------------------------------------------------------------- outline
    def shape(self, layer, width=0.1):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetLayer(layer)
        s.SetWidth(FromMM(width))
        self.board.Add(s)
        return s

    def line(self, x1, y1, x2, y2, layer=pcbnew.Edge_Cuts, width=0.1):
        s = self.shape(layer, width)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(x1, y1))
        s.SetEnd(P(x2, y2))
        return s

    def arc(self, sx, sy, mx, my, ex, ey, layer=pcbnew.Edge_Cuts, width=0.1):
        s = self.shape(layer, width)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(sx, sy), P(mx, my), P(ex, ey))
        return s

    def rounded_rect(self, x0, y0, x1, y1, r, layer=pcbnew.Edge_Cuts, width=0.1):
        k = r * (1 - math.sqrt(0.5))
        self.line(x0 + r, y0, x1 - r, y0, layer, width)
        self.line(x1, y0 + r, x1, y1 - r, layer, width)
        self.line(x1 - r, y1, x0 + r, y1, layer, width)
        self.line(x0, y1 - r, x0, y0 + r, layer, width)
        self.arc(x1 - r, y0, x1 - k, y0 + k, x1, y0 + r, layer, width)
        self.arc(x1, y1 - r, x1 - k, y1 - k, x1 - r, y1, layer, width)
        self.arc(x0 + r, y1, x0 + k, y1 - k, x0, y1 - r, layer, width)
        self.arc(x0, y0 + r, x0 + k, y0 + k, x0 + r, y0, layer, width)

    def outline(self):
        W, H, r = D.BOARD_W, D.BOARD_H, D.BOARD_CORNER_R
        k = r * (1 - math.sqrt(0.5))
        # notch for the mid-mount USB-C (TYPE-C-31-M-14: 9.35 x 6.05 mm cutout open to the edge)
        j3 = self.fps["J3"]
        ux, uy = pcbnew.ToMM(j3.GetPosition().x), pcbnew.ToMM(j3.GetPosition().y)
        nx0, nx1, ny = ux - 4.675, ux + 4.675, uy - 3.35
        self.line(r, 0, W - r, 0)
        self.line(W, r, W, H - r)
        self.line(W - r, H, nx1, H)
        self.line(nx1, H, nx1, ny)
        self.line(nx1, ny, nx0, ny)
        self.line(nx0, ny, nx0, H)
        self.line(nx0, H, r, H)
        self.line(0, H - r, 0, r)
        self.arc(W - r, 0, W - k, k, W, r)
        self.arc(W, H - r, W - k, H - k, W - r, H)
        self.arc(r, H, k, H - k, 0, H - r)
        self.arc(0, r, k, k, r, 0)
        # FPC slot: two lines + two semicircles
        x0, y0, x1, y1 = D.FPC_SLOT
        rs = (y1 - y0) / 2
        cy = (y0 + y1) / 2
        self.line(x0 + rs, y0, x1 - rs, y0)
        self.line(x1 - rs, y1, x0 + rs, y1)
        self.arc(x1 - rs, y0, x1, cy, x1 - rs, y1)
        self.arc(x0 + rs, y1, x0, cy, x0 + rs, y0)

    def text(self, txt, x, y, layer=pcbnew.B_SilkS, size=1.0, thick=0.15, mirrored=None, angle=0):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(txt)
        t.SetPosition(P(x, y))
        t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(thick))
        t.SetTextAngleDegrees(angle)
        if mirrored is None:
            mirrored = layer in (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_Fab)
        t.SetMirrored(mirrored)
        self.board.Add(t)
        return t

    def silkscreen(self):
        bx0, by0, bx1, by1 = D.BATTERY_POCKET
        for (a, b, c, d) in [(bx0, by0, bx1, by0), (bx1, by0, bx1, by1), (bx1, by1, bx0, by1), (bx0, by1, bx0, by0)]:
            self.line(a, b, c, d, pcbnew.B_SilkS, 0.15)
        self.text("LiPo <=2.0mm  150-300mAh  (PCM)", (bx0 + bx1) / 2, (by0 + by1) / 2, size=1.4, thick=0.2)
        cx0, cy0, cx1, cy1 = D.NFC_COIL_RECT
        self.text("NFC", (cx0 + cx1) / 2, (cy0 + cy1) / 2 - 2, size=3.0, thick=0.4)
        self.text("tap phone here (front)", (cx0 + cx1) / 2, (cy0 + cy1) / 2 + 2.5, size=1.0, thick=0.15)
        for txt, x, y, size, thick in D.SILK_BACK:
            self.text(txt, x, y, size=size, thick=thick)
        # front side marking for the panel & NFC tap area
        self.text("4.2\" BWRY e-paper glued here (91x77)", D.BOARD_W / 2, D.PANEL_H / 2, layer=pcbnew.F_SilkS, size=1.5, thick=0.2)

    # ------------------------------------------------------------ tracks/vias
    def track(self, x1, y1, x2, y2, net, layer=pcbnew.B_Cu, width=0.5, locked=True):
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(P(x1, y1))
        t.SetEnd(P(x2, y2))
        t.SetWidth(FromMM(width))
        t.SetLayer(layer)
        t.SetNet(self.net(net))
        t.SetLocked(locked)
        self.board.Add(t)
        return t

    def via(self, x, y, net, locked=True):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(P(x, y))
        v.SetDrill(FromMM(0.3))
        v.SetWidth(FromMM(0.6))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.net(net))
        v.SetLocked(locked)
        self.board.Add(v)
        return v

    def pad_pos(self, ref, number):
        fp = self.fps[ref]
        for pad in fp.Pads():
            if pad.GetNumber() == number:
                p = pad.GetPosition()
                return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        raise KeyError((ref, number))

    def nfc_note(self):
        import gen_nfc_footprint as N
        L, d_in = N.inductance_uH()
        f0 = 1 / (2 * math.pi * math.sqrt(L * 1e-6 * 28.5e-12)) / 1e6
        print(f"NFC coil (footprint ANT1): L ~ {L:.2f} uH -> f0 ~ {f0:.2f} MHz with ST25DV 28.5 pF (target 13.56 MHz)")

    # ------------------------------------------------------------------ zones
    def rule_area(self, rect, layers, no_pour=True, no_footprints=False, no_tracks=False, no_vias=False, name=""):
        x0, y0, x1, y1 = rect
        z = pcbnew.ZONE(self.board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowCopperPour(no_pour)
        z.SetDoNotAllowFootprints(no_footprints)
        z.SetDoNotAllowTracks(no_tracks)
        z.SetDoNotAllowVias(no_vias)
        z.SetDoNotAllowPads(False)
        lset = pcbnew.LSET()
        for l in layers:
            lset.addLayer(l)
        z.SetLayerSet(lset)
        z.SetZoneName(name)
        ol = z.Outline()
        ol.NewOutline()
        for (x, y) in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
            ol.Append(FromMM(x), FromMM(y))
        self.board.Add(z)
        return z

    def gnd_pour(self, layer, pad_connection=None):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(layer)
        z.SetNet(self.net("GND"))
        z.SetAssignedPriority(0)
        # Solid connection on both layers; B.Cu islands get stitching vias in route_pcb.py.
        if pad_connection is None:
            pad_connection = pcbnew.ZONE_CONNECTION_FULL
        z.SetPadConnection(pad_connection)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetLocalClearance(FromMM(0.25))
        z.SetMinThickness(FromMM(0.2))
        z.SetThermalReliefGap(FromMM(0.3))
        z.SetThermalReliefSpokeWidth(FromMM(0.4))
        z.SetZoneName(f"GND_{pcbnew.LayerName(layer)}")
        ol = z.Outline()
        ol.NewOutline()
        m = 0.5
        for (x, y) in [(m, m), (D.BOARD_W - m, m), (D.BOARD_W - m, D.BOARD_H - m), (m, D.BOARD_H - m)]:
            ol.Append(FromMM(x), FromMM(y))
        self.board.Add(z)
        return z

    def zones(self):
        cu = [pcbnew.F_Cu, pcbnew.B_Cu]
        x0, y0, x1, y1 = D.NFC_COIL_RECT
        self.rule_area((x0 - 1.0, y0 - 1.0, x1 + 1.0, y1 + 1.0), cu, no_pour=True, no_tracks=True, no_vias=True, name="NFC coil: no copper / no routing")
        self.rule_area(D.ESP_ANT_KEEPOUT, cu, no_pour=True, no_tracks=True, no_vias=True, name="ESP32-C3 antenna keepout")
        self.rule_area(D.BATTERY_POCKET, [pcbnew.B_Cu], no_pour=False, no_footprints=True, name="battery pocket: no parts")
        sx0, sy0, sx1, sy1 = D.FPC_SLOT
        self.rule_area((sx0 - 0.8, sy0 - 0.8, sx1 + 0.8, sy1 + 0.8), cu, no_pour=True, no_tracks=True, no_vias=True, name="FPC slot")
        self.gnd_pour(pcbnew.F_Cu)
        self.gnd_pour(pcbnew.B_Cu)

    def fill(self):
        # ZONE_FILLER segfaults on a board created in memory; round-trip through disk so the
        # board gets a proper project/connectivity context first.
        pcbnew.SaveBoard(OUT, self.board)
        self.board = pcbnew.LoadBoard(OUT)
        self.board.BuildConnectivity()
        filler = pcbnew.ZONE_FILLER(self.board)
        filler.Fill(self.board.Zones())

    def save(self):
        pcbnew.SaveBoard(OUT, self.board)
        print("wrote", OUT)

    def report(self):
        b = self.board
        n_tracks = sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_TRACK")
        n_vias = sum(1 for t in b.GetTracks() if t.GetClass() == "PCB_VIA")
        print(f"{len(list(b.GetFootprints()))} footprints, {n_tracks} track segments, {n_vias} vias, {len(list(b.Zones()))} zones")
        # unrouted check via connectivity
        b.BuildConnectivity()
        conn = b.GetConnectivity()
        unrouted = conn.GetUnconnectedCount(True)
        print("unrouted connections:", unrouted)
        return unrouted


def main():
    g = Gen()
    for n in D.all_nets():
        g.net(n)
    g.place_parts()
    g.apply_net_classes()
    g.outline()
    g.silkscreen()
    g.nfc_note()
    g.zones()
    g.fill()
    g.save()
    g.report()


if __name__ == "__main__":
    main()
