"""Run in the KiCad10 GUI console. Read-only PCB contact evidence."""
from pathlib import Path
import json,hashlib,pcbnew
H=Path('/workspace/scratch/200245c5fbc3/chroma-badge/hardware/portrait/enclosure')
P=H.parent/'pcb/badge.kicad_pcb'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected='a6e52a432d860a8ce0d489fdaac9a9f9a56ae2c96e7ca05ce998e5b3b5a1cd40'
assert sha(P)==expected and str(pcbnew.GetBuildVersion()).startswith('10.')
b=pcbnew.LoadBoard(str(P))
def rect(obj):
 q=obj.GetBoundingBox();return [pcbnew.ToMM(q.GetX()),pcbnew.ToMM(q.GetY()),pcbnew.ToMM(q.GetRight()),pcbnew.ToMM(q.GetBottom())]
pads=[]
for f in b.GetFootprints():
 for p in f.Pads():
  r=rect(p);exp=max(pcbnew.ToMM(p.GetSolderMaskExpansion(pcbnew.F_Mask)),pcbnew.ToMM(p.GetSolderMaskExpansion(pcbnew.B_Mask)))
  pads.append({'ref':f.GetReference(),'number':p.GetNumber(),'bbox':r,'mask_expansion_mm':exp,'mask_bbox':[r[0]-exp,r[1]-exp,r[2]+exp,r[3]+exp],'front_mask':p.IsOnLayer(pcbnew.F_Mask),'back_mask':p.IsOnLayer(pcbnew.B_Mask),'drill_mm':[pcbnew.ToMM(p.GetDrillSize().x),pcbnew.ToMM(p.GetDrillSize().y)]})
vias=[]
for t in b.GetTracks():
 if type(t).__name__=='PCB_VIA':
  vias.append({'bbox':rect(t),'drill_mm':pcbnew.ToMM(t.GetDrillValue()),'policy':'Conservatively exclude every via annulus, whether tented or not'})
report={'board_sha256':expected,'engine':pcbnew.GetBuildVersion(),'script_sha256':sha(Path(__file__)),'pads':pads,'vias':vias,'footprint_count':len(list(b.GetFootprints())),'limits':['Bounding rectangles are conservative projections, not actual mask polygon tessellation.','No local bearing-height or mask wear qualification is inferred.']}
assert report['footprint_count']==81 and sha(P)==expected
(H/'validation/pcb_contact_inputs.json').write_text(json.dumps(report,indent=2)+'\n')
print('CONTACT INPUTS',len(pads),'pads',len(vias),'vias; frozen PCB unchanged')
