"""Read candidate PCB with KiCad Python, preserving per-reference coverage.
Run only inside the KiCad 10 GUI Scripting Console. Does not save or mutate the PCB.
"""
from pathlib import Path
import json,hashlib,re,os
import pcbnew
H=Path(__file__).resolve().parent;ROOT=H.parents[2];PCB=ROOT/'hardware/portrait/pcb/badge.kicad_pcb'
b=pcbnew.LoadBoard(str(PCB));parts=[]
log=(H/'validation/pcb_snapshot/step_export.log').read_text()
step=(H/'output/pcb_actual_export.step').read_text()
labels=set(re.findall(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(\s*'[^']*'\s*,\s*'([^']+)'",step,re.S))
fprefs={fp.GetReference() for fp in b.GetFootprints()}
added=labels & fprefs
missing=set(re.findall(r'Could not add 3D model (?:to|for) (\S+)\.',log))-added
assert len(fprefs)==81 and re.search(r'\b10\.',pcbnew.GetBuildVersion()), 'Need final81 in KiCad10' 
for fp in b.GetFootprints():
 ref=fp.GetReference();name=str(fp.GetFPID().GetLibItemName());graphics=[s for s in fp.GraphicalItems() if s.GetLayer()==pcbnew.B_CrtYd]
 boxes=[s.GetBoundingBox() for s in graphics] or [fp.GetBoundingBox(False,False)]
 x0=min(pcbnew.ToMM(r.GetX()) for r in boxes);y0=min(pcbnew.ToMM(r.GetY()) for r in boxes)
 x1=max(pcbnew.ToMM(r.GetRight()) for r in boxes);y1=max(pcbnew.ToMM(r.GetBottom()) for r in boxes)
 # Deliberately conservative candidate heights, never implied selected-MPN max.
 if ref=='U1': h=2.6;basis='ESP32-C3 module nominal2.4 plus0.2 solder/envelope margin'
 elif ref=='J1':h=1.1;basis='Hirose drawing body1.0 plus0.1 envelope margin; board orientation/entry pending'
 elif ref=='J2':h=5.8;basis='JST official ePH.pdf page4 SMT side-entry body5.5 plus0.3 engineering margin; plug lead exit remains unverified'
 elif ref=='J3':h=2.86;basis='HRO nominal8.94x7.96x2.86 body envelope crosses board plane; source-derived, not detailed pin/lug or mating CAD'
 elif ref=='C100':h=3.0;basis='Samsung CL32A107MQVNNNE body max2.8 plus0.2 engineering/solder budget'
 elif 'SMA' in name:h=2.7;basis='AssumedSMA package envelope; MPN height unverified'
 elif 'SOT' in name:h=1.5;basis='AssumedSOT package envelope; MPN height unverified'
 elif 'SOD' in name:h=1.5;basis='AssumedSOD123 envelope; MPN height unverified'
 elif 'FNR4018' in name:h=2.1;basis='Nominal1.8mm inductor family plus0.3 margin; exact MPN unverified'
 elif '0805' in name:h=1.6;basis='Selected TDK body max1.45 plus0.15 solder/engineering height allowance'
 elif '0603' in name:h=1.0;basis='Assumed0603 envelope; exact MPN maxheight unverified'
 elif '0402' in name:h=.65;basis='Assumed0402 envelope; exact MPN maxheight unverified'
 elif ref.startswith('SW'):h=2.8;basis='C&K officialPTS810 body2.5 +0.2/-0.1; envelope2.8 includes0.1 solder margin; chosenforce/travel still verify'
 elif ref.startswith('TP'):h=.1;basis='Bare test pad, no fitted tall pin'
 else:h=2.4;basis='UNKNOWN package; budget placeholder only'
 models=[m.m_Filename for m in fp.Models()]
 parts.append({'pcb_side':str(b.GetLayerName(fp.GetLayer())),'ref':ref,'value':fp.GetValue(),'footprint':name,'position_mm':[pcbnew.ToMM(fp.GetPosition().x),pcbnew.ToMM(fp.GetPosition().y)],'rotation_deg':fp.GetOrientationDegrees(),'xy_envelope_front_rect_mm':[x0,y0,x1,y1],'xy_basis':'B.CrtYd with stroke' if graphics else 'footprint bbox fallback','height_budget_mm':h,'height_basis':basis,'models':models,'step_coverage':'ADDED' if ref in added else 'MISSING_REFERENCED_FILE' if ref in missing else 'NO_MODEL_IN_EXPORT','classification':'PROXY_ENVELOPE_NOT_MANUFACTURER_SOLID' if ref in ('J2','J3') else 'MODEL' if ref in added else 'PROXY_REQUIRED'})
parts.sort(key=lambda p:p['ref'])
report={'kicad_python_version':pcbnew.GetBuildVersion(),'model_export_evidence':'Reference assembly labels in actual STEP, not pre-load Adding component log; not a detailed-solid completeness claim','full_step_sha256':hashlib.sha256((H/'output/pcb_actual_export.step').read_bytes()).hexdigest(),'bare_step_sha256':hashlib.sha256((H/'output/pcb_board_body.step').read_bytes()).hexdigest(),'board':str(PCB.relative_to(ROOT)),'board_sha256':hashlib.sha256(PCB.read_bytes()).hexdigest(),'footprint_count':len(parts),'added_refs':sorted(added),'missing_referenced_refs':sorted(missing),'unmodeled_refs':sorted(p['ref'] for p in parts if p['step_coverage']=='NO_MODEL_IN_EXPORT'),'parts':parts,'rule':'Per-reference height envelopes are assumptions until MPN/vendor drawings prove maxheight; no full assembly pass'}
(H/'validation/pcb_model_coverage.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='parts'},indent=2))
