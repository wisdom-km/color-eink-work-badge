from pathlib import Path
import pcbnew
b = pcbnew.GetBoard()
assert pcbnew.Version().startswith('10.')
name = b.GetFileName()
assert name.endswith('/hardware/portrait/pcb/badge.kicad_pcb')
pad = next(p for p in b.FindFootprintByReference('R103').Pads() if p.GetNumber() == '1')
assert pad.GetNetname() == 'RESEC'
assert pad.GetPosition() == pcbnew.VECTOR2I_MM(33.9125,74)
n = pad.GetNetCode()
tracks = list(b.GetTracks())
assert sum(not isinstance(t,pcbnew.PCB_VIA) for t in tracks) == 961
assert sum(isinstance(t,pcbnew.PCB_VIA) for t in tracks) == 110
assert any(isinstance(t,pcbnew.PCB_VIA) and t.GetNetCode()==n and t.GetPosition()==pcbnew.VECTOR2I_MM(19.65,81.4) for t in tracks)
backup = Path(name).with_name('before_resec_local_bridge.kicad_pcb')
assert not backup.exists()
assert pcbnew.SaveBoard(str(backup),b)
assert b.GetFileName() == name
F,B = pcbnew.F_Cu,pcbnew.B_Cu
routes = [
(F,(19.65,81.4),(20.25,70)),
(B,(20.25,70),(22.35,70.3)),
(F,(22.35,70.3),(27.35,75.3)),
(B,(27.35,75.3),(30.45,76.8)),
(B,(30.45,76.8),(34.55,77)),
(F,(34.55,77),(34.85,74.35)),
(B,(34.85,74.35),(33.9125,74))]
points = [(20.25,70),(22.35,70.3),(27.35,75.3),(34.55,77),(34.85,74.35)]
for layer,a,c in routes:
    t=pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I_MM(*a))
    t.SetEnd(pcbnew.VECTOR2I_MM(*c))
    t.SetWidth(pcbnew.FromMM(0.2))
    t.SetLayer(layer)
    t.SetNetCode(n)
    b.Add(t)
for p in points:
    v=pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I_MM(*p))
    v.SetWidth(pcbnew.FromMM(0.6))
    v.SetDrill(pcbnew.FromMM(0.3))
    v.SetLayerPair(F,B)
    v.SetNetCode(n)
    b.Add(v)
pcbnew.Refresh()
print('Added only RESEC: 7 tracks, 5 vias. Save, refill, and run full DRC now.')
