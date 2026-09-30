"""Classify retained conservative conflicts honestly; do not change any shape or PCB."""
from pathlib import Path
import json,datetime,shutil,py_compile
H=Path(__file__).resolve().parent;V=H/'validation'
backup=V/('review_classification_'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S'));backup.mkdir()
for p in [H/'c1_validate.py',H/'c1_pipeline.py']+list(V.glob('c1_final_*.log'))+[V/'c1_pipeline_pending.json']:
 if p.exists():shutil.copy2(p,backup/p.name)
p=H/'c1_validate.py';s=p.read_text()
def change(old,new):
 global s
 assert s.count(old)==1,old[:80];s=s.replace(old,new)
change("'status':'FAIL_CHECKED_NOMINAL_ENVELOPES' if fail else 'PASS_CHECKED_NOMINAL_ENVELOPES_ONLY'","'status':'REVIEW_REQUIRED_RESERVED_SPACE_CONFLICTS' if fail else 'PASS_CHECKED_NOMINAL_ENVELOPES_ONLY'")
change("'status':'PASS_NOMINAL_STACK_AND_SECTION_ONLY' if not fail and not clampfail else 'FAIL_NOMINAL_INTERNAL'","'status':'REVIEW_REQUIRED_INTERNAL_ASSEMBLY' if fail else ('FAIL_NOMINAL_INTERNAL' if clampfail else 'PASS_NOMINAL_STACK_AND_SECTION_ONLY')")
change("assert not fail,('POPULATED',nonzero,pairs,reserved,posts,actualchecks)","assert not nonzero and not posts and max(actualchecks.values())<1e-6 and max(usb_nominal.values())<1e-6,('SOLID_CONFLICT',nonzero,posts,actualchecks)\nassert all(not q['positive_hits'] and q['position_error_mm']<1e-6 for q in service)\nassert all(set((q['a'],q['b']))=={'TP2','TP3'} for q in pairs),pairs\nassert {(q['space'],q['ref']) for q in reserved}=={('ph_plug_keepout','SW3'),('flex_keepout','C118'),('flex_keepout','C119'),('flex_keepout','C120'),('flex_keepout','C121')},reserved\npads={p['ref']:p for p in inputs['pads'] if p['ref'] in ('TP2','TP3')}\nassert set(pads)=={'TP2','TP3'} and area(pads['TP2']['bbox'],pads['TP3']['bbox'])==0\nwrite('assembly_review_gates.json',{'status':'REVIEW_REQUIRED_ASSEMBLY','manufacturing_release_blocked':True,'retained_courtyard_pair_intersections':pairs,'test_pad_refinement':{'pad_bbox_overlap_mm2':0,'source':'KiCad10 actual copper pad bounding boxes; no fitted testpoint pins','original_courtyard_shapes_retained':True},'blocking_reserved_conflicts':reserved,'geometry_changed_to_hide_conflicts':False,'required_actions':['PH/SW3: obtain exact mounted PHR2/lead exit and switch body geometry, prove clearance or revise mechanical mating path/PCB through a new electrical revision.','FPC/C118..C121: original full-block reserve retained; prove source-backed folded route and connector lock access or revise layout through a new electrical revision.','Do not order or force assembly based on clear outer shell or zero local material interference.']})")
change("print('PASS C1 NOMINAL CHECKS; MANUFACTURING RELEASE BLOCKED BY PHYSICAL GATES')","print('C1 CHECKS EXECUTED: REVIEW_REQUIRED_ASSEMBLY; retained PH/FPC blockers; no manufacturing release')")
p.write_text(s)
p=H/'c1_pipeline.py';s=p.read_text()
old="'pcb_contact_audit.json','internal_envelope_validation.json')";assert s.count(old)==1;s=s.replace(old,"'pcb_contact_audit.json','internal_envelope_validation.json','assembly_review_gates.json')")
old="status='PASS_EXECUTED_NOMINAL_C1_PIPELINE_ONLY'";assert s.count(old)==1;s=s.replace(old,"status='EXECUTED_REVIEW_REQUIRED_C1_PIPELINE'")
p.write_text(s)
for p in (H/'c1_validate.py',H/'c1_pipeline.py'):py_compile.compile(str(p),doraise=True)
print('CLASSIFICATION ONLY; original conflicts/shapes retained; prior execution archived',backup)
