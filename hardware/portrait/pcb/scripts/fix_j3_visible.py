from pathlib import Path
import shutil
import pcbnew
b=pcbnew.GetBoard()
assert pcbnew.Version().startswith('10.')
board=Path(b.GetFileName())
assert board.name=='badge.kicad_pcb' and board.parent.name=='pcb'
j=b.FindFootprintByReference('J3')
assert j.GetPosition()==pcbnew.VECTOR2I_MM(50,89.94)
assert j.GetOrientationDegrees()==180 and j.GetLayer()==pcbnew.B_Cu
assert not any(s.GetLayer()==pcbnew.B_CrtYd for s in j.GraphicalItems())
lib=board.parent/'lib/badge.pretty/TYPE-C-31-M-14.kicad_mod'
s=lib.read_text()
old='(fp_rect (start -5.825 -4.98) (end 5.825 3.48)'
new='(fp_rect (start -6.33 -4.99) (end 6.33 3.48)'
assert s.count(old)==1 and '(attr through_hole)' in s
backup=board.with_name('before_j3_final_fix.kicad_pcb')
assert not backup.exists()
assert pcbnew.SaveBoard(str(backup),b)
shutil.copy2(lib,str(lib)+'.before_pad_courtyard')
moves=[]
for ref,x in [('R1',44),('R2',55.5)]:
    f=b.FindFootprintByReference(ref)
    assert f.GetPosition()==pcbnew.VECTOR2I_MM(x,84)
    assert f.GetOrientationDegrees()==-90
    ends=[]
    for p in f.Pads():
        q=p.GetPosition()
        for t in b.GetTracks():
            if isinstance(t,pcbnew.PCB_VIA): continue
            for end in (False,True):
                v=t.GetEnd() if end else t.GetStart()
                if v==q:
                    assert t.GetNetCode()==p.GetNetCode()
                    ends.append((t,end,pcbnew.VECTOR2I(v.x,v.y-pcbnew.FromMM(0.15))))
    assert len(ends)==3,(ref,len(ends))
    moves.append((f,x,ends))
lib.write_text(s.replace(old,new))
j.SetAttributes((j.GetAttributes() & ~pcbnew.FP_SMD) | pcbnew.FP_THROUGH_HOLE)
r=pcbnew.PCB_SHAPE(j)
r.SetShape(pcbnew.SHAPE_T_RECT)
r.SetStart(pcbnew.VECTOR2I_MM(56.33,84.95))
r.SetEnd(pcbnew.VECTOR2I_MM(43.67,93.42))
r.SetWidth(pcbnew.FromMM(0.05))
r.SetLayer(pcbnew.B_CrtYd)
j.Add(r)
for f,x,ends in moves:
    f.SetPosition(pcbnew.VECTOR2I_MM(x,83.85))
    for t,end,q in ends:
        if end: t.SetEnd(q)
        else: t.SetStart(q)
pcbnew.Refresh()
print('J3 attributes/courtyard synchronized; R1/R2 shifted with 6 exact attached endpoints. Save/refill/full DRC.')
