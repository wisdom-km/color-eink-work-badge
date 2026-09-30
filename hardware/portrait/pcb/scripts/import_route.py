"""Import local routing, synchronize source placements with localized trace removal.
Does not generate a fresh un-routed board or modify H2.
"""
from pathlib import Path
import sys, math
import pcbnew
sys.path.insert(0,str(Path(__file__).resolve().parent));import design as D
P=Path(__file__).resolve().parents[1];board=P/'badge.kicad_pcb'
b=pcbnew.LoadBoard(str(board))
if '--import-only' in sys.argv:
 assert pcbnew.ImportSpecctraSES(b,str(P/'output/badge-local.ses'))
 pcbnew.SaveBoard(str(board),b)
 print('SES imported and saved; run --post-only in a fresh pcbnew process')
 raise SystemExit(0)
if '--post-only' not in sys.argv: raise SystemExit('Use --import-only, then --post-only in a fresh process (KiCad9 SWIG plugin lifecycle)')
removed=0;moved=[]
for part in D.PARTS:
 fp=next(f for f in b.GetFootprints() if f.GetReference()==part.ref)
 target=pcbnew.VECTOR2I(pcbnew.FromMM(part.at[0]),pcbnew.FromMM(part.at[1]))
 old=fp.GetPosition()
 if (old-target).EuclideanNorm()>1000:
  boxes=[]
  box=fp.GetBoundingBox();box.Inflate(pcbnew.FromMM(1));boxes.append(box)
  fp.Move(target-old)
  box=fp.GetBoundingBox();box.Inflate(pcbnew.FromMM(1));boxes.append(box)
  for t in list(b.GetTracks()):
   if any(box.Intersects(t.GetBoundingBox()) for box in boxes): b.Remove(t);removed+=1
  moved.append(part.ref)
b.BuildConnectivity();pcbnew.SaveBoard(str(board),b)
b=pcbnew.LoadBoard(str(board));pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(board),b)
print('Imported localSES; moved',moved,'local track/via removals',removed,'tracks+vias',len(list(b.GetTracks())))
