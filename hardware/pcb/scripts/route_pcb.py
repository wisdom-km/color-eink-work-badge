"""Autoroute hardware/pcb/badge.kicad_pcb with Freerouting, then stitch isolated GND islands.

Run after gen_pcb.py:   python3 route_pcb.py [--skip-route]
Steps: DSN export -> Freerouting -> SES import -> zone fill -> DRC (kicad-cli, JSON) ->
add GND vias next to GND pads that are not tied to the ground pour -> repeat -> final DRC.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import time

import pcbnew
from pcbnew import VECTOR2I, FromMM

sys.path.insert(0, os.path.dirname(__file__))
import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
PCB_DIR = os.path.abspath(os.path.join(HERE, ".."))
BOARD = os.path.join(PCB_DIR, "badge.kicad_pcb")
OUT_DIR = os.path.join(PCB_DIR, "output")
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _first_file(*paths):
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


def _resolve_freerouting_jar():
    found = _first_file(
        os.path.join(REPO_ROOT, "tools", "freerouting", "freerouting.jar"),
        "/opt/freerouting/freerouting.jar",
    )
    return found or os.path.join(REPO_ROOT, "tools", "freerouting", "freerouting.jar")


def _resolve_java():
    found = _first_file(
        os.path.join(REPO_ROOT, "tools", "jre", "bin", "java.exe"),
        os.path.join(REPO_ROOT, "tools", "jre", "bin", "java"),
        "/opt/freerouting/jre25/bin/java",
    )
    if found:
        return found
    return shutil.which("java") or os.path.join(REPO_ROOT, "tools", "jre", "bin", "java")


FREEROUTING_JAR = _resolve_freerouting_jar()
JAVA = _resolve_java()


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def export_dsn(board):
    """Export the Specctra DSN with the GND pours removed, so Freerouting routes GND with
    tracks like any other net. Otherwise it treats the pour as a plane, routes nothing for GND
    and the dense B.Cu routing chops the pour into islands with unconnected pads."""
    dsn = os.path.join(OUT_DIR, "badge.dsn")
    pours = [z for z in board.Zones() if not z.GetIsRuleArea()]
    for z in pours:
        board.Remove(z)
    try:
        if not pcbnew.ExportSpecctraDSN(board, dsn):
            raise RuntimeError("DSN export failed")
    finally:
        for z in pours:
            board.Add(z)
    return dsn


def run_freerouting(board):
    ses = os.path.join(OUT_DIR, "badge.ses")
    if os.path.exists(ses):
        os.remove(ses)
    dsn = export_dsn(board)
    java = JAVA if os.path.exists(JAVA) else "java"
    # Freerouting 2.4 writes an empty .ses when given an absolute output path -> run inside OUT_DIR
    cmd = [java, "-jar", FREEROUTING_JAR, "-de", os.path.basename(dsn), "-do", os.path.basename(ses),
           "-mp", "100", "-mt", "1"]
    print("running (cwd=output):", " ".join(cmd), flush=True)
    # Output must go to a file, not a pipe: with piped stdout Freerouting exits before its
    # asynchronous session save completes and leaves an empty .ses behind.
    # ...and, empirically, only when launched through os.system(): with subprocess.run() the
    # JVM exits before the save thread writes anything (0-byte .ses), so we shell out here.
    log = os.path.join(OUT_DIR, "freerouting.log")
    if os.name == "nt":
        def _cmd_quote(s):
            return '"' + s.replace('"', '""') + '"'
        os.system(
            "cd /d {cwd} && {line} > {log} 2>&1".format(
                cwd=_cmd_quote(OUT_DIR),
                line=" ".join(_cmd_quote(c) for c in cmd),
                log=_cmd_quote(log),
            )
        )
    else:
        import shlex
        os.system(
            f"cd {shlex.quote(OUT_DIR)} && {' '.join(shlex.quote(c) for c in cmd)} > {shlex.quote(log)} 2>&1"
        )
    with open(log) as lf:
        lines = [l.rstrip() for l in lf if "nalytics" not in l and l.strip()]
    print("\n".join(lines[-6:]), flush=True)
    last = -1
    for _ in range(90):
        size = os.path.getsize(ses) if os.path.exists(ses) else 0
        if size > 0 and size == last:
            break
        last = size
        time.sleep(1)
    if not os.path.exists(ses) or os.path.getsize(ses) == 0:
        raise RuntimeError("Freerouting produced no .ses")
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise RuntimeError("SES import failed")


def fill(board):
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()


def enforce_netclass_widths(board, skip_nets=None):
    """F05: Freerouting/SES often necks Power/NFC below design.py minima. Widen in place.

    GND is skipped: the pour is the current path (>> 0.3 mm). Widening Freerouting
    GND stubs into via clearance is not a real Power-width fix.
    """
    skip = set(skip_nets or ("GND",))
    want = {}
    for spec in D.NET_CLASSES.values():
        for netname in spec["nets"]:
            if netname in skip:
                continue
            want[netname] = FromMM(spec["track"])
    n = 0
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        w = want.get(t.GetNetname())
        if w is None or t.GetWidth() >= w:
            continue
        t.SetWidth(w)
        n += 1
    return n


def drc_json(path):
    """Run error-level DRC and return the JSON for this invocation only.

    kicad-cli may return 0 (report written) or 5 (violations / injected failure).
    A non-zero code without a *new* report used to fall through to a leftover
    empty file and look like a clean board. Never open a pre-existing report.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    rpt = os.path.join(OUT_DIR, "drc_run_%s_%s.json" % (os.getpid(), time.time_ns()))
    r = subprocess.run(
        ["kicad-cli", "pcb", "drc", "--severity-error", "--format", "json", "-o", rpt, path],
        capture_output=True, text=True,
    )
    # 0 = CLI wrote a report. 5 is used by --exit-code-violations and by the
    # F19 fault probe; it is only usable if this run created `rpt`.
    if r.returncode not in (0, 5):
        raise RuntimeError(
            "kicad-cli pcb drc failed rc=%s stderr=%s"
            % (r.returncode, (r.stderr or "").strip())
        )
    if not os.path.isfile(rpt) or os.path.getsize(rpt) == 0:
        raise RuntimeError(
            "kicad-cli pcb drc rc=%s produced no new report; refusing to read any older DRC file"
            % r.returncode
        )
    try:
        with open(rpt, encoding="utf-8") as f:
            return json.load(f)
    finally:
        try:
            os.remove(rpt)
        except OSError:
            pass


def isolated_gnd_pads(report):
    """Return [(x, y)] of GND pads listed in 'unconnected_items' violations."""
    pads = []
    for v in report.get("unconnected_items", []):
        for it in v.get("items", []):
            d = it.get("description", "")
            if d.startswith("Pad") and "[GND]" in d:
                pads.append((it["pos"]["x"], it["pos"]["y"]))
    # de-duplicate
    return sorted(set(pads))


class Stitcher:
    def __init__(self, board):
        self.board = board
        self.gnd = board.FindNet("GND")

    def via_fits(self, x, y, via_d=0.6, drill=0.3, clr=0.22, ignore=None):
        """True if a GND stitching via can be placed at (x, y) mm.

        Same-net copper is allowed (via-in-pad / overlap with the pour). Other nets
        use pad.HitTest rather than the bounding-box diagonal, which was rejecting
        every candidate next to elongated SOIC / FPC pads.
        """
        if x < 0.8 or y < 0.8 or x > D.BOARD_W - 0.8 or y > D.BOARD_H - 0.8:
            return False
        for rect in (D.NFC_COIL_RECT, D.ESP_ANT_KEEPOUT, D.FPC_SLOT):
            if rect[0] - 0.4 <= x <= rect[2] + 0.4 and rect[1] - 0.4 <= y <= rect[3] + 0.4:
                return False
        p = P(x, y)
        r_via = FromMM(via_d / 2)
        extra = FromMM(clr)
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetCode() == self.gnd.GetNetCode():
                    continue
                if pad.HitTest(p, r_via + extra):
                    return False
        circle = pcbnew.SHAPE_CIRCLE(p, r_via)
        for t in self.board.GetTracks():
            if ignore is not None and t is ignore:
                continue
            if t.GetClass() == "PCB_VIA":
                min_d = FromMM(0.55 if t.GetNetCode() == self.gnd.GetNetCode() else via_d / 2 + 0.3 + clr)
                if (t.GetPosition() - p).EuclideanNorm() < min_d:
                    return False
                continue
            if t.GetNetCode() == self.gnd.GetNetCode():
                continue
            seg = pcbnew.SHAPE_SEGMENT(t.GetStart(), t.GetEnd(), t.GetWidth())
            if seg.Collide(circle, extra):
                return False
        return True

    def add_via(self, x, y, via_d=0.6, drill=0.3):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(P(x, y))
        v.SetDrill(FromMM(drill))
        v.SetWidth(FromMM(via_d))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.gnd)
        self.board.Add(v)

    def add_track(self, x1, y1, x2, y2, w=0.3):
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(P(x1, y1))
        t.SetEnd(P(x2, y2))
        t.SetWidth(FromMM(w))
        t.SetLayer(pcbnew.B_Cu)
        t.SetNet(self.gnd)
        self.board.Add(t)

    def stitch(self, pads):
        added = 0
        for (px, py) in pads:
            done = False
            for radius in (1.0, 1.3, 1.7, 2.2, 2.8):
                for k in range(16):
                    ang = k * math.pi / 8
                    x, y = px + radius * math.cos(ang), py + radius * math.sin(ang)
                    if self.via_fits(x, y):
                        self.add_via(x, y)
                        self.add_track(px, py, x, y)
                        added += 1
                        done = True
                        break
                if done:
                    break
            if not done:
                print(f"    could not place a stitching via near GND pad at ({px:.2f}, {py:.2f})")
        return added

    def _poly_area_mm2(self, outline):
        return abs(outline.Area()) / 1e12

    def _point_inside(self, outline, x, y):
        return outline.PointInside(P(x, y))

    def _island_candidates(self, outline, pads_mm):
        """Candidate via locations: GND pads on the island, then a bbox grid."""
        bb = outline.BBox()
        x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
        x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
        pts = []
        for (px, py) in pads_mm:
            if self._point_inside(outline, px, py):
                pts.append((px, py))
                for dx, dy in ((0.4, 0), (-0.4, 0), (0, 0.4), (0, -0.4),
                               (0.6, 0), (-0.6, 0), (0, 0.6), (0, -0.6)):
                    pts.append((px + dx, py + dy))
        n = 18
        for i in range(n):
            for j in range(n):
                x = x0 + (x1 - x0) * (i + 0.5) / n
                y = y0 + (y1 - y0) * (j + 0.5) / n
                pts.append((x, y))
        # centroid (may fall outside a concave island)
        n_pt = outline.PointCount()
        if n_pt:
            cx = sum(pcbnew.ToMM(outline.CPoint(j).x) for j in range(n_pt)) / n_pt
            cy = sum(pcbnew.ToMM(outline.CPoint(j).y) for j in range(n_pt)) / n_pt
            pts.insert(0, (cx, cy))
        out = []
        seen = set()
        for x, y in pts:
            key = (round(x, 2), round(y, 2))
            if key in seen:
                continue
            seen.add(key)
            if self._point_inside(outline, x, y):
                out.append((x, y))
        return out

    def _gnd_polys(self):
        out = {}
        for z in self.board.Zones():
            if z.GetIsRuleArea() or z.GetNetCode() != self.gnd.GetNetCode():
                continue
            polys = z.GetFilledPolysList(z.GetLayer())
            if polys is None:
                continue
            islands = [(self._poly_area_mm2(polys.COutline(i)), i, polys.COutline(i))
                       for i in range(polys.OutlineCount())]
            islands.sort(reverse=True)
            out[z.GetLayer()] = islands
        return out

    def apply_esp_gnd_nettie(self):
        """ESP32-C3-MINI-1 GND pins are internally commoned; tell KiCad so split
        pours under the module are not flagged as separate nets."""
        fp = self.board.FindFootprintByReference("U1")
        if fp is None:
            return 0
        key = "1,2,11,14,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53"
        try:
            groups = [str(g) for g in (fp.GetNetTiePadGroups() or [])]
        except TypeError:
            groups = []
        if groups == [key]:
            return 0
        if hasattr(fp, "ClearNetTiePadGroups"):
            fp.ClearNetTiePadGroups()
            fp.AddNetTiePadGroup(key)
            return 1
        if any("36" in g and "1" in g for g in groups):
            return 0
        fp.AddNetTiePadGroup(key)
        return 1

    def apply_extra_gnd_pads(self):
        """J1 pin 7 is NC Keep Open (GDEM042F86 p.7). Must not stitch it to GND."""
        fp = self.board.FindFootprintByReference("J1")
        if fp is None:
            return 0
        n = 0
        for pad in fp.Pads():
            if pad.GetNumber() == "7" and pad.GetNetCode() == self.gnd.GetNetCode():
                pad.SetNetCode(0)
                n += 1
        return n

    def stitch_grid(self, step=8.0):
        """Via grid in the battery pocket: ties the main B.Cu pour to the main F.Cu pour."""
        added = 0
        x0, y0, x1, y1 = D.BATTERY_POCKET
        y = y0 + 5.0
        while y < y1 - 3.0:
            x = x0 + 5.0
            while x < x1 - 3.0:
                if self.via_fits(x, y):
                    self.add_via(x, y)
                    added += 1
                x += step
            y += step
        return added

    def stitch_islands(self, require_other_main=False):
        """Place one GND via in every filled-pour island that is not already stitched.

        Prefer locations that also sit on the other layer's main pour, so the via
        merges the island into the same copper cluster instead of creating a new one.
        """
        gnd_pads = []
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetCode() == self.gnd.GetNetCode():
                    p = pad.GetPosition()
                    gnd_pads.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
        sizes = ((0.6, 0.3), (0.5, 0.3), (0.45, 0.2), (0.4, 0.2))
        gnd_vias = []
        for t in self.board.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetCode() == self.gnd.GetNetCode():
                p = t.GetPosition()
                gnd_vias.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
        layers = self._gnd_polys()
        other_main = {
            pcbnew.B_Cu: (layers.get(pcbnew.F_Cu) or [None])[0][2] if layers.get(pcbnew.F_Cu) else None,
            pcbnew.F_Cu: (layers.get(pcbnew.B_Cu) or [None])[0][2] if layers.get(pcbnew.B_Cu) else None,
        }
        added = 0
        missed = 0
        for layer, islands in layers.items():
            if len(islands) <= 1:
                continue
            main_other = other_main.get(layer)
            for area, idx, ol in islands[1:]:
                already = False
                for vx, vy in gnd_vias:
                    if not self._point_inside(ol, vx, vy):
                        continue
                    if require_other_main and main_other is not None and not self._point_inside(main_other, vx, vy):
                        continue
                    already = True
                    break
                if already:
                    continue
                cands = self._island_candidates(ol, gnd_pads)
                if main_other is not None:
                    cands.sort(key=lambda xy: (0 if self._point_inside(main_other, xy[0], xy[1]) else 1))
                placed = False
                for (x, y) in cands:
                    if require_other_main and main_other is not None and not self._point_inside(main_other, x, y):
                        continue
                    for via_d, drill in sizes:
                        if self.via_fits(x, y, via_d=via_d, drill=drill):
                            self.add_via(x, y, via_d=via_d, drill=drill)
                            gnd_vias.append((x, y))
                            added += 1
                            placed = True
                            break
                    if placed:
                        break
                if not placed:
                    missed += 1
                    bb = ol.BBox()
                    print(f"    could not stitch GND island layer={pcbnew.LayerName(layer)}#{idx} "
                          f"area={area:.2f} mm2 bbox=({pcbnew.ToMM(bb.GetLeft()):.1f},"
                          f"{pcbnew.ToMM(bb.GetTop()):.1f})-"
                          f"({pcbnew.ToMM(bb.GetRight()):.1f},{pcbnew.ToMM(bb.GetBottom()):.1f})")
        return added, missed

    def _gnd_via_tracks(self):
        return [t for t in self.board.GetTracks()
                if t.GetClass() == "PCB_VIA" and t.GetNetCode() == self.gnd.GetNetCode()]

    def _island_blocker_vias(self, island_ol, fmain):
        """GND vias on a leftover B.Cu island that do not land on F.Cu main."""
        out = []
        for t in self._gnd_via_tracks():
            p = t.GetPosition()
            x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
            if not self._point_inside(island_ol, x, y):
                continue
            if self._point_inside(fmain, x, y):
                continue
            w, drill = self._via_size(t)
            out.append((t, x, y, w, drill))
        return out

    def _copper_clusters(self):
        """Union-find of filled GND polygons joined by GND vias. Returns
        (items, find, groups, main_root) where leftover clusters are those
        whose find(k) != main_root."""
        layers = self._gnd_polys()
        items = []
        for layer, islands in layers.items():
            for area, idx, ol in islands:
                items.append((f"{layer}:{idx}", area, ol, layer, idx))
        gnd_vias = [(pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y))
                    for t in self._gnd_via_tracks()]
        parent = {k: k for k, _a, _o, _l, _i in items}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, c):
            ra, rc = find(a), find(c)
            if ra != rc:
                parent[rc] = ra

        for vx, vy in gnd_vias:
            hit = [k for k, _a, ol, _l, _i in items if self._point_inside(ol, vx, vy)]
            for a, c in zip(hit, hit[1:]):
                union(a, c)
        groups = {}
        for k, area, ol, layer, idx in items:
            groups.setdefault(find(k), []).append((k, area, ol, layer, idx))
        main_root = max(groups, key=lambda r: sum(a for _k, a, _o, _l, _i in groups[r]))
        return items, find, groups, main_root, layers

    def stitch_leftover_to_main(self):
        """For electrically leftover B.Cu islands, place an overlap via onto F.Cu main.

        Occupying vias that miss F.Cu main are only removed if an overlap via can
        actually be placed; otherwise they are restored so cluster/jumper still work.
        """
        items, find, groups, main_root, layers = self._copper_clusters()
        if pcbnew.F_Cu not in layers or pcbnew.B_Cu not in layers:
            return 0
        fmain = layers[pcbnew.F_Cu][0][2]
        leftover_b = [(area, idx, ol) for k, area, ol, layer, idx in items
                      if layer == pcbnew.B_Cu and find(k) != main_root]
        if not leftover_b:
            return 0
        pads = []
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetCode() == self.gnd.GetNetCode():
                    p = pad.GetPosition()
                    pads.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
        added = 0
        sizes = ((0.4, 0.2, 0.22), (0.45, 0.2, 0.22), (0.5, 0.3, 0.22),
                 (0.4, 0.2, 0.20), (0.45, 0.2, 0.20))
        extra_pts = [(51.39, 54.55), (51.50, 54.45), (66.09, 49.62), (66.09, 49.47)]

        def overlap_cands(ol):
            cands = [xy for xy in self._island_candidates(ol, pads)
                     if self._point_inside(fmain, xy[0], xy[1])]
            bb = ol.BBox()
            x0, y0 = pcbnew.ToMM(bb.GetLeft()) - 3.0, pcbnew.ToMM(bb.GetTop()) - 3.0
            x1, y1 = pcbnew.ToMM(bb.GetRight()) + 3.0, pcbnew.ToMM(bb.GetBottom()) + 3.0
            n = 28
            for i in range(n):
                for j in range(n):
                    x = x0 + (x1 - x0) * (i + 0.5) / n
                    y = y0 + (y1 - y0) * (j + 0.5) / n
                    if self._point_inside(fmain, x, y) and self._point_inside(ol, x, y):
                        cands.append((x, y))
            for xy in extra_pts:
                if self._point_inside(ol, xy[0], xy[1]) and self._point_inside(fmain, xy[0], xy[1]):
                    cands.insert(0, xy)
            return cands, x0, y0, x1, y1

        def try_overlap(ol, area):
            cands, x0, y0, x1, y1 = overlap_cands(ol)
            seen = set()
            for via_d, drill, clr in sizes:
                for x, y in cands:
                    key = (round(x, 3), round(y, 3), via_d, clr)
                    if key in seen:
                        continue
                    seen.add(key)
                    if not self._point_inside(ol, x, y) or not self._point_inside(fmain, x, y):
                        continue
                    if self.via_fits(x, y, via_d=via_d, drill=drill, clr=clr):
                        self.add_via(x, y, via_d=via_d, drill=drill)
                        print(f"    leftover overlap via ({x:.2f},{y:.2f}) d={via_d} clr={clr:.2f} "
                              f"island {area:.2f} mm2")
                        return True
            island_pads = [(x, y) for x, y in pads if self._point_inside(ol, x, y)]
            n = 28
            for i in range(n):
                for j in range(n):
                    x = x0 + (x1 - x0) * (i + 0.5) / n
                    y = y0 + (y1 - y0) * (j + 0.5) / n
                    if not self._point_inside(fmain, x, y):
                        continue
                    if not self.via_fits(x, y, via_d=0.5, drill=0.3):
                        continue
                    for px, py in island_pads or [(pcbnew.ToMM(ol.CPoint(0).x), pcbnew.ToMM(ol.CPoint(0).y))]:
                        if self._jumper_fits(pcbnew.B_Cu, px, py, x, y):
                            self.add_via(x, y, via_d=0.5, drill=0.3)
                            self.add_track(px, py, x, y, w=0.25)
                            print(f"    leftover via+track ({px:.2f},{py:.2f})->({x:.2f},{y:.2f}) "
                                  f"island {area:.2f} mm2")
                            return True
            return False

        for area, idx, ol in leftover_b:
            if try_overlap(ol, area):
                added += 1
                continue
            blockers = self._island_blocker_vias(ol, fmain)
            if not blockers:
                print(f"    leftover island B.Cu#{idx} {area:.2f} mm2 still open")
                continue
            for t, x, y, w, drill in blockers:
                print(f"    removed blocker GND via ({x:.2f},{y:.2f}) not on F.Cu main")
                self.board.Remove(t)
            if try_overlap(ol, area):
                added += 1
                continue
            for _t, x, y, w, drill in blockers:
                self.add_via(x, y, via_d=w, drill=drill)
                print(f"    restored occupying GND via ({x:.2f},{y:.2f})")
            print(f"    leftover island B.Cu#{idx} {area:.2f} mm2 still open")
        return added

    def stitch_cluster_overlaps(self):
        """Via at the overlap of a leftover F.Cu island and a main-cluster B.Cu island."""
        layers = self._gnd_polys()
        if pcbnew.F_Cu not in layers or pcbnew.B_Cu not in layers:
            return 0
        items = []
        for layer, islands in layers.items():
            for area, idx, ol in islands:
                items.append((f"{layer}:{idx}", area, ol, layer))
        gnd_vias = []
        for t in self.board.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetCode() == self.gnd.GetNetCode():
                p = t.GetPosition()
                gnd_vias.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
        parent = {k: k for k, _a, _o, _l in items}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, c):
            ra, rc = find(a), find(c)
            if ra != rc:
                parent[rc] = ra

        for vx, vy in gnd_vias:
            hit = [k for k, _a, ol, _l in items if self._point_inside(ol, vx, vy)]
            for a, c in zip(hit, hit[1:]):
                union(a, c)
        groups = {}
        for k, area, ol, layer in items:
            groups.setdefault(find(k), []).append((k, area, ol, layer))
        main_root = max(groups, key=lambda r: sum(a for _k, a, _o, _l in groups[r]))
        main_b = [ol for k, area, ol, layer in groups[main_root] if layer == pcbnew.B_Cu]
        leftover_f = [ol for k, area, ol, layer in items
                      if layer == pcbnew.F_Cu and find(k) != main_root]
        added = 0
        sizes = ((0.6, 0.3, 0.22), (0.5, 0.3, 0.22), (0.4, 0.2, 0.22), (0.4, 0.2, 0.20))
        for fol in leftover_f:
            bb = fol.BBox()
            x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
            x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
            placed = False
            for i in range(20):
                for j in range(20):
                    x = x0 + (x1 - x0) * (i + 0.5) / 20
                    y = y0 + (y1 - y0) * (j + 0.5) / 20
                    if not self._point_inside(fol, x, y):
                        continue
                    if not any(self._point_inside(bol, x, y) for bol in main_b):
                        continue
                    for via_d, drill, clr in sizes:
                        if self.via_fits(x, y, via_d=via_d, drill=drill, clr=clr):
                            self.add_via(x, y, via_d=via_d, drill=drill)
                            added += 1
                            placed = True
                            print(f"    cluster-overlap via ({x:.2f},{y:.2f})")
                            break
                    if placed:
                        break
                if placed:
                    break
        return added

    def jumper_islands(self):
        """Bridge leftover B.Cu GND clusters to the main cluster with short tracks."""
        layers = self._gnd_polys()
        if pcbnew.B_Cu not in layers:
            return 0
        items = []  # (key, ol) all GND filled polys
        for layer, islands in layers.items():
            for area, idx, ol in islands:
                items.append((f"{layer}:{idx}", area, ol, layer))
        gnd_vias = []
        for t in self.board.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetCode() == self.gnd.GetNetCode():
                p = t.GetPosition()
                gnd_vias.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
        parent = {k: k for k, _a, _o, _l in items}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, c):
            ra, rc = find(a), find(c)
            if ra != rc:
                parent[rc] = ra

        for vx, vy in gnd_vias:
            hit = [k for k, _a, ol, _l in items if self._point_inside(ol, vx, vy)]
            for a, c in zip(hit, hit[1:]):
                union(a, c)
        groups = {}
        for k, area, ol, layer in items:
            groups.setdefault(find(k), []).append((k, area, ol, layer))
        main_root = max(groups, key=lambda r: sum(a for _k, a, _o, _l in groups[r]))
        merged_b = [ol for k, area, ol, layer in groups[main_root] if layer == pcbnew.B_Cu]
        leftover = [(area, ol) for k, area, ol, layer in items
                    if layer == pcbnew.B_Cu and find(k) != main_root]
        added = 0
        for area, ol in leftover:
            n = ol.PointCount()
            step_i = max(1, n // 50)
            src = [(pcbnew.ToMM(ol.CPoint(j).x), pcbnew.ToMM(ol.CPoint(j).y))
                   for j in range(0, n, step_i)]
            dst = []
            for mol in merged_b:
                step = max(1, mol.PointCount() // 100)
                for j in range(0, mol.PointCount(), step):
                    dst.append((pcbnew.ToMM(mol.CPoint(j).x), pcbnew.ToMM(mol.CPoint(j).y)))
            pairs = [((px - mx) ** 2 + (py - my) ** 2, px, py, mx, my)
                     for px, py in src for mx, my in dst]
            pairs.sort()
            placed = False
            for best in pairs[:120]:
                if best[0] ** 0.5 > 4.0:
                    break
                _, x1, y1, x2, y2 = best
                if self._jumper_fits(pcbnew.B_Cu, x1, y1, x2, y2):
                    t = pcbnew.PCB_TRACK(self.board)
                    t.SetStart(P(x1, y1))
                    t.SetEnd(P(x2, y2))
                    t.SetWidth(FromMM(0.25))
                    t.SetLayer(pcbnew.B_Cu)
                    t.SetNet(self.gnd)
                    self.board.Add(t)
                    added += 1
                    placed = True
                    print(f"    jumper B.Cu {x1:.2f},{y1:.2f} -> {x2:.2f},{y2:.2f} "
                          f"({best[0]**0.5:.2f} mm, island {area:.2f} mm2)")
                    break
            if not placed:
                bb = ol.BBox()
                print(f"    no jumper for leftover island {area:.2f} mm2 "
                      f"bbox=({pcbnew.ToMM(bb.GetLeft()):.1f},{pcbnew.ToMM(bb.GetTop()):.1f})-"
                      f"({pcbnew.ToMM(bb.GetRight()):.1f},{pcbnew.ToMM(bb.GetBottom()):.1f})")
        return added

    def _jumper_fits(self, layer, x1, y1, x2, y2):
        for rect in (D.NFC_COIL_RECT, D.ESP_ANT_KEEPOUT, D.FPC_SLOT):
            sx0, sx1 = min(x1, x2), max(x1, x2)
            sy0, sy1 = min(y1, y2), max(y1, y2)
            if sx1 >= rect[0] - 0.4 and sx0 <= rect[2] + 0.4 and sy1 >= rect[1] - 0.4 and sy0 <= rect[3] + 0.4:
                return False
        seg = pcbnew.SHAPE_SEGMENT(P(x1, y1), P(x2, y2), FromMM(0.25))
        extra = FromMM(0.22)
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetCode() == self.gnd.GetNetCode():
                    continue
                try:
                    sh = pad.GetEffectiveShape(layer)
                except TypeError:
                    sh = pad.GetEffectiveShape()
                if sh is not None and sh.Collide(seg, extra):
                    return False
        for t in self.board.GetTracks():
            if t.GetNetCode() == self.gnd.GetNetCode():
                continue
            if t.GetClass() == "PCB_VIA":
                via = pcbnew.SHAPE_CIRCLE(t.GetPosition(), FromMM(0.3))
                if seg.Collide(via, extra):
                    return False
                continue
            if t.GetLayer() != layer:
                continue
            other = pcbnew.SHAPE_SEGMENT(t.GetStart(), t.GetEnd(), t.GetWidth())
            if other.Collide(seg, extra):
                return False
        return True

    def _via_size(self, via):
        try:
            w = pcbnew.ToMM(via.GetWidth(pcbnew.F_Cu))
        except TypeError:
            w = pcbnew.ToMM(via.GetWidth())
        return w, pcbnew.ToMM(via.GetDrill())

    def nudge_clearance_vias(self, report):
        """Slide GND vias that fail copper clearance by a fraction of a millimetre.

        Tight leftover/cluster vias can land ~0.18 mm from a Power-class track
        (DRC wants 0.20). A 0.1–0.2 mm shift is enough and keeps the via on the
        same pour overlap.
        """
        uuid_map = {}
        for t in self.board.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetCode() == self.gnd.GetNetCode():
                uuid_map[t.m_Uuid.AsString()] = t
        targets = []
        seen = set()
        for v in report.get("violations", []):
            if "clearance" not in str(v.get("type", "")):
                continue
            for it in v.get("items", []):
                via = uuid_map.get(it.get("uuid", ""))
                if via is None:
                    continue
                uid = via.m_Uuid.AsString()
                if uid in seen:
                    continue
                seen.add(uid)
                targets.append(via)
        moved = 0
        for via in targets:
            x0 = pcbnew.ToMM(via.GetPosition().x)
            y0 = pcbnew.ToMM(via.GetPosition().y)
            via_d, drill = self._via_size(via)
            placed = False
            for radius in (0.08, 0.12, 0.16, 0.20, 0.25):
                for k in range(16):
                    ang = k * math.pi / 8
                    x = x0 + radius * math.cos(ang)
                    y = y0 + radius * math.sin(ang)
                    if not self.via_fits(x, y, via_d=via_d, drill=drill, clr=0.22, ignore=via):
                        continue
                    via.SetPosition(P(x, y))
                    moved += 1
                    placed = True
                    print(f"    nudged GND via ({x0:.2f},{y0:.2f}) -> ({x:.2f},{y:.2f})")
                    break
                if placed:
                    break
            if not placed:
                print(f"    could not nudge GND via at ({x0:.2f},{y0:.2f})")
        return moved


class Fixups:
    """Repair the small connectivity gaps the Freerouting -> SES -> KiCad round trip leaves behind."""

    def __init__(self, board, stitcher):
        self.board = board
        self.st = stitcher

    def item(self, uuid):
        it = self.board.GetItem(pcbnew.KIID(uuid))
        if it is None or it.GetClass() == "DELETED_BOARD_ITEM":
            return None
        return it.Cast()

    def join_duplicate_pads(self):
        """Pads sharing a number inside one footprint (tactile switches) are internally
        connected in the part; give KiCad a copper link so connectivity agrees."""
        n = 0
        for fp in self.board.GetFootprints():
            # only tactile switches need this; ANT1 is handled by its custom pad, J3's shield
            # pads are tied together by the GND pour
            if not fp.GetReference().startswith("SW"):
                continue
            groups = {}
            for pad in fp.Pads():
                if pad.GetNetCode() > 0:
                    groups.setdefault(pad.GetNumber(), []).append(pad)
            for num, pads in groups.items():
                for a, b in zip(pads, pads[1:]):
                    already = False
                    for t in self.board.GetTracks():
                        if t.GetClass() != "PCB_TRACK":
                            continue
                        s, e = t.GetStart(), t.GetEnd()
                        if ((s == a.GetPosition() and e == b.GetPosition()) or
                                (s == b.GetPosition() and e == a.GetPosition())):
                            already = True
                            break
                    if already:
                        continue
                    t = pcbnew.PCB_TRACK(self.board)
                    t.SetStart(a.GetPosition())
                    t.SetEnd(b.GetPosition())
                    t.SetWidth(FromMM(0.4))
                    t.SetLayer(pcbnew.B_Cu)
                    t.SetNet(a.GetNet())
                    self.board.Add(t)
                    n += 1
        return n

    def repair(self, report):
        """Extend dangling track ends into their pad / add a via where a B.Cu track meets an F.Cu track."""
        fixed = 0
        for v in report.get("unconnected_items", []):
            items = v.get("items", [])
            if len(items) != 2:
                continue
            objs = [self.item(it["uuid"]) for it in items]
            descs = [it.get("description", "") for it in items]
            if any(o is None for o in objs):
                continue
            kinds = [o.GetClass() for o in objs]
            if "PCB_TRACK" in kinds and "PAD" in kinds:
                tr = objs[kinds.index("PCB_TRACK")]
                pad = objs[kinds.index("PAD")]
                pp = pad.GetPosition()
                d_start = (tr.GetStart() - pp).EuclideanNorm()
                d_end = (tr.GetEnd() - pp).EuclideanNorm()
                if min(d_start, d_end) < FromMM(3.0):
                    if d_start < d_end:
                        tr.SetStart(pp)
                    else:
                        tr.SetEnd(pp)
                    fixed += 1
            elif kinds == ["PCB_TRACK", "PCB_TRACK"] and objs[0].GetLayer() != objs[1].GetLayer():
                best = None
                for pa in (objs[0].GetStart(), objs[0].GetEnd()):
                    for pb in (objs[1].GetStart(), objs[1].GetEnd()):
                        d = (pa - pb).EuclideanNorm()
                        if best is None or d < best[0]:
                            best = (d, pa)
                if best and best[0] < FromMM(0.6):
                    x, y = pcbnew.ToMM(best[1].x), pcbnew.ToMM(best[1].y)
                    via = pcbnew.PCB_VIA(self.board)
                    via.SetPosition(best[1])
                    via.SetDrill(FromMM(0.3))
                    via.SetWidth(FromMM(0.6))
                    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                    via.SetNet(objs[0].GetNet())
                    self.board.Add(via)
                    fixed += 1
        return fixed


def pad_pad_unrouted(report):
    n = 0
    for v in report.get("unconnected_items", []):
        descs = [it.get("description", "") for it in v.get("items", [])]
        if len(descs) == 2 and all(d.startswith("Pad") for d in descs) and not any("[GND]" in d for d in descs):
            n += 1
    return n


def summarize(report):
    counts = {}
    for k in ("violations", "unconnected_items", "schematic_parity"):
        for viol in report.get(k, []):
            t = viol.get("type", k)
            counts[t] = counts.get(t, 0) + 1
    return counts


def unconnected_pairs(report):
    """Human-readable list of unconnected item pairs that are NOT GND-pour related."""
    out = []
    for v in report.get("unconnected_items", []):
        descs = [it.get("description", "") for it in v.get("items", [])]
        if not any("[GND]" in d for d in descs):
            out.append(" <-> ".join(descs))
    return out


def main():
    board = pcbnew.LoadBoard(BOARD)
    ds = board.GetDesignSettings()
    ds.m_ViasMinSize = FromMM(0.4)
    ds.m_MinThroughDrill = FromMM(0.2)
    if "--export-dsn" in sys.argv:
        print("wrote", export_dsn(board))
        return 0
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    st = Stitcher(board)
    fx = Fixups(board, st)
    print("joined duplicate pads with", fx.join_duplicate_pads(), "tracks", flush=True)
    # --import-only: a badge.ses already exists in output/ (e.g. Freerouting was run by hand
    #                from a shell, see README) -> import it and do the fix-up/stitching passes.
    # --skip-route:  do not touch routing at all, only fix-ups + GND stitching on the saved board.
    import_only = "--import-only" in sys.argv
    rounds = 0 if "--skip-route" in sys.argv else (1 if import_only else 2)
    for rnd in range(rounds):
        if import_only:
            ses = os.path.join(OUT_DIR, "badge.ses")
            if not pcbnew.ImportSpecctraSES(board, ses):
                raise RuntimeError("SES import failed")
        else:
            run_freerouting(board)
        fill(board)
        n_w = enforce_netclass_widths(board)
        print(f"   enforced netclass widths on {n_w} tracks", flush=True)
        fill(board)
        pcbnew.SaveBoard(BOARD, board)
        rep = drc_json(BOARD)
        n = fx.repair(rep)
        print(f"routing round {rnd}: repaired {n} gaps; DRC: {summarize(rep)}", flush=True)
        fill(board)
        pcbnew.SaveBoard(BOARD, board)
        rep = drc_json(BOARD)
        if pad_pad_unrouted(rep) == 0:
            break
        print(f"   {pad_pad_unrouted(rep)} pad-to-pad connections still unrouted -> another Freerouting round", flush=True)
    fill(board)
    pcbnew.SaveBoard(BOARD, board)
    if rounds == 0:
        rep = drc_json(BOARD)
        print("repaired", fx.repair(rep), "gaps")
        fill(board)
        pcbnew.SaveBoard(BOARD, board)

    print("ESP GND net-tie:", st.apply_esp_gnd_nettie(), flush=True)
    print("J1 pin 7 NC Keep Open (cleared GND if present):", st.apply_extra_gnd_pads(), flush=True)
    fill(board)
    n_grid = st.stitch_grid()
    print(f"battery-pocket GND via grid: {n_grid}", flush=True)
    fill(board)
    pcbnew.SaveBoard(BOARD, board)

    n_via, missed = st.stitch_islands(require_other_main=False)
    print(f"GND island stitch (any): added {n_via} vias, {missed} islands still open", flush=True)
    if n_via:
        fill(board)
        pcbnew.SaveBoard(BOARD, board)
    n_via2, missed = st.stitch_islands(require_other_main=True)
    print(f"GND island stitch (to main): added {n_via2} vias, {missed} islands still open", flush=True)
    if n_via2:
        fill(board)
        pcbnew.SaveBoard(BOARD, board)

    n_left = st.stitch_leftover_to_main()
    print(f"leftover-to-main stitch: {n_left}", flush=True)
    if n_left:
        fill(board)
        pcbnew.SaveBoard(BOARD, board)
        n_left2 = st.stitch_leftover_to_main()
        print(f"leftover-to-main stitch (retry): {n_left2}", flush=True)
        if n_left2:
            fill(board)
            pcbnew.SaveBoard(BOARD, board)

    n_ov = st.stitch_cluster_overlaps()
    print(f"cluster-overlap vias: {n_ov}", flush=True)
    if n_ov:
        fill(board)
        pcbnew.SaveBoard(BOARD, board)

    n_jmp = st.jumper_islands()
    print(f"GND island jumpers: {n_jmp}", flush=True)
    if n_jmp:
        fill(board)
        pcbnew.SaveBoard(BOARD, board)

    for it in range(5):
        fill(board)
        pcbnew.SaveBoard(BOARD, board)
        rep = drc_json(BOARD)
        n = st.nudge_clearance_vias(rep)
        print(f"via clearance nudge {it}: moved {n}; DRC: {summarize(rep)}", flush=True)
        if n == 0:
            break

    for it in range(8):
        rep = drc_json(BOARD)
        pads = isolated_gnd_pads(rep)
        print(f"GND pad stitch pass {it}: {len(pads)} isolated GND pads; DRC: {summarize(rep)}", flush=True)
        if not pads:
            break
        n = st.stitch(pads)
        print(f"    added {n} vias", flush=True)
        if n == 0:
            break
        fill(board)
        pcbnew.SaveBoard(BOARD, board)

    n_w = enforce_netclass_widths(board)
    print(f"final netclass width enforce: {n_w} tracks", flush=True)
    fill(board)
    pcbnew.SaveBoard(BOARD, board)
    rep = drc_json(BOARD)
    counts = summarize(rep)
    n_tracks = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK")
    n_vias = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
    print(f"final: {n_tracks} track segments, {n_vias} vias; DRC (errors only): {counts or 'clean'}")
    for line in unconnected_pairs(rep):
        print("   unrouted:", line)
    with open(os.path.join(OUT_DIR, "drc_final.json"), "w") as f:
        json.dump(rep, f, indent=1)
    return 0 if not counts else 1


if __name__ == "__main__":
    sys.exit(main())
