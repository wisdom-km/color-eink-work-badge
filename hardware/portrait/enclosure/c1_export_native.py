"""C1 native B export and explicit KiCad raw-frame verification. Run freecad-python."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,'/usr/lib/freecad/lib')
import FreeCAD as App, Part
import c1_config as K
H=Path(__file__).resolve().parent;O=H/'output';V=H/'validation'
C=json.loads((O/'mechanical_dimensions.json').read_text())['canonical']
meta=K.fingerprints(C);assert meta['board_sha256']==K.BOARD_SHA
plan=json.loads((V/'mechanical_expectation.json').read_text())
coverage=json.loads((V/'pcb_model_coverage.json').read_text())
assert coverage['board_sha256']==K.BOARD_SHA and coverage['footprint_count']==81
sha=K.digest
assert coverage['full_step_sha256']==sha(O/'pcb_actual_export.step')
def read(p):
 s=Part.Shape();s.read(str(p));assert s.isValid();return s
def bounds(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def near(a,b,t=.002):return max(abs(x-y) for x,y in zip(a,b))<t
raw=read(O/'pcb_board_body.step');full=read(O/'pcb_actual_export.step')
raw_expected=[0,-92.64,0,58,0,.710]
frame_errors=[]
if not near(bounds(raw),raw_expected):frame_errors.append('RAW_CORE_BOUNDS')
usb=[];other=[]
for s in full.Solids:
 b=s.BoundBox
 if near([b.XLength,b.YLength,b.ZLength],[8.94,7.96,2.86]):usb.append(s)
 elif not near(bounds(s),bounds(raw)):
  other.append(bounds(s))
usb_expected=[45.53,-93.17,-2.095,54.47,-85.21,.765]
if len(usb)!=1 or not near(bounds(usb[0]),usb_expected):frame_errors.append('USB_SOURCE_MODEL_POSE')
if any(b[5]>.001 for b in other):frame_errors.append('OTHER_COMPONENTS_NOT_BACK_SIDE')
probes=[]
for x,y,inside in [(5,-5,True),(27.1,-88.7,False),(50,-90,False),(10,-90,True)]:
 observed=raw.isInside(App.Vector(x,y,.355),1e-6,True)
 probes.append({'xy':[x,y],'inside':observed,'expected':inside})
 if observed!=inside:frame_errors.append('OUTLINE_SLOT_PROBE')
translation=C['retention']['raw_to_mechanical_z']
mapped=raw.copy();mapped.translate(App.Vector(0,0,translation))
mapped_full=full.copy();mapped_full.translate(App.Vector(0,0,translation))
frame={**meta,'status':'FAIL_RAW_EXPORT_FRAME' if frame_errors else 'PASS_RAW_EXPORT_FRAME_ONLY','failures':frame_errors,'raw_core_bbox':bounds(raw),'mapped_core_bbox':bounds(mapped),'raw_full_bbox':bounds(full),'mapped_full_bbox':bounds(mapped_full),'raw_usb_bboxes':[bounds(s) for s in usb],'other_back_component_bboxes':other,'inside_probes':probes,'translation_mm':[0,0,translation],'raw_step_sha256':sha(O/'pcb_actual_export.step'),'bare_step_sha256':sha(O/'pcb_board_body.step'),'model_datum_raw_mm':-.085,'mapped_model_standoff_mm':-.040,'source':K.SOURCES['step_datum'],'limits':['KiCad generic component origin includes BOARD_OFFSET0.05 plus B.Cu0.035; finished mask-frame map adds0.045.','HRO actual mounting datum and0.75-vs0.8mm board fit require first article. No arbitrary model offset correction.']}
(V/'pcb_step_frame.json').write_text(json.dumps(frame,indent=2)+'\n')
assert not frame_errors,frame
A=O/'portrait_assembly.FCStd';a_hash=sha(A) if A.exists() else None
path=O/'portrait_assembly_revisionB.FCStd'
doc=App.newDocument('PortraitRevisionBC1')
for name,key,category in K.OBJECTS:
 f='portrait_'+key+'.step' if category=='structure' else 'reference_'+key+'.step'
 shape=read(O/f);assert len(shape.Solids)==1,name
 ob=doc.addObject('Part::Feature',name);ob.Shape=shape
 ob.addProperty('App::PropertyString','EvidenceStatus','C1');ob.EvidenceStatus='Nominal candidate; geometry only; physical gates remain open'
 ob.addProperty('App::PropertyString','ShapeCategory','C1');ob.ShapeCategory=category
 ob.addProperty('App::PropertyString','EditableSource','C1');ob.EditableSource='build_enclosure.py + c1_config.py + c1_geometry.py; electrical sources read-only'
 if category=='space_reserve':ob.Label=name+' [clearance reserve, not routed wire]'
 if category=='audit':ob.Label=name+' [audit only, not physical part]'
for p in coverage['parts']:
 if p['ref']=='J3':continue
 x0,y0,x1,y1=p['xy_envelope_front_rect_mm'];h=p['height_budget_mm']
 ob=doc.addObject('Part::Feature','Envelope_'+p['ref'])
 ob.Label=p['ref']+' [height envelope]';ob.Shape=Part.makeBox(x1-x0,y1-y0,h,App.Vector(x0,-y1,-h))
 ob.addProperty('App::PropertyString','HeightEvidence','C1');ob.HeightEvidence=p['height_basis']
 ob.addProperty('App::PropertyString','ShapeCategory','C1');ob.ShapeCategory='component_proxy'
assert sorted(o.Name for o in doc.Objects)==sorted(plan['expected_shape_names'])
doc.recompute();doc.saveAs(str(path));App.closeDocument(doc.Name)
check=App.openDocument(str(path))
parts={o.Name:{'valid':o.Shape.isValid(),'solids':len(o.Shape.Solids),'volume_mm3':o.Shape.Volume} for o in check.Objects}
assert sorted(parts)==sorted(plan['expected_shape_names']) and all(p['valid'] and p['solids']==1 for p in parts.values())
report={**meta,'status':'PASS_NATIVE_BREP_READBACK_ONLY','native_file':path.name,'native_sha256':sha(path),'raw_step_sha256':sha(O/'pcb_actual_export.step'),'expected_shape_names':plan['expected_shape_names'],'expected_shape_count':plan['expected_shape_count'],'reference_shape_names':plan['reference_shape_names'],'parts':parts,'freecad_version':App.Version()[:3],'limits':['80 explicit height envelopes plus sourced J3 box; not81 vendor models.','Editable BREP features; dimension edit is in C1 Python sources, not a fabricated sketch history.','Headless visibility is not GUI proof; see native_gui_readback.json after actual save/reopen.']}
(V/'freecad_readback.json').write_text(json.dumps(report,indent=2)+'\n');App.closeDocument(check.Name)
assert not a_hash or sha(A)==a_hash
print('PASS FRAME + NATIVE BREP',len(parts),'objects; historical A unchanged')
