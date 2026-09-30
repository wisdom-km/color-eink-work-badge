"""C1 nominal OCC checks. Clear geometry is not physical manufacturing approval."""
import json,itertools
import cadquery as cq
import build_enclosure as M
import c1_config as K
from cad_helpers import front_box,overlap_volume,inspect,render_shapes
V=M.REPORT;O=M.OUT;T=M.C['retention'];meta=K.fingerprints(M.C)
coverage=json.loads((V/'pcb_model_coverage.json').read_text());plan=json.loads((V/'mechanical_expectation.json').read_text())
assert meta['board_sha256']==coverage['board_sha256']==K.BOARD_SHA
assert coverage['footprint_count']==81 and coverage['full_step_sha256']==K.digest(O/'pcb_actual_export.step')
framegate=json.loads((V/'pcb_step_frame.json').read_text());assert framegate['status']=='PASS_RAW_EXPORT_FRAME_ONLY'
by={p['ref']:p for p in coverage['parts']}
for name,xy in {'SW3':(3,46),'R21':(14.5,60.1),'R1':(44.2,83.85),'R2':(55.5,83.85),'J2':(9,54)}.items():
 assert max(abs(a-b) for a,b in zip(by[name]['position_mm'],xy))<1e-6,name
assert abs(by['J2']['rotation_deg']%360)<1e-6
assert all(p['pcb_side']=='B.Cu' for p in coverage['parts'])
case={'front_frame':M.frame(),'back_cover':M.cover()};refs=M.reference_bodies()
bodies={p['ref']:front_box(p['xy_envelope_front_rect_mm'],-p['height_budget_mm'],0) for p in coverage['parts'] if p['ref']!='J3'}
bodies['J3']=refs['usb_outline']
def ov(a,b):
 x,y=a.BoundingBox(),b.BoundingBox()
 if min(x.xmax,y.xmax)<=max(x.xmin,y.xmin)+1e-8 or min(x.ymax,y.ymax)<=max(x.ymin,y.ymin)+1e-8 or min(x.zmax,y.zmax)<=max(x.zmin,y.zmin)+1e-8:return 0.
 return max(0.,overlap_volume(a,b))
def area(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
def write(name,r):
 r.update(meta);(V/name).write_text(json.dumps(r,indent=2)+'\n');print(name,r.get('status'),flush=True)
nonzero=[];rows=[]
for ref,s in bodies.items():
 tests={name:ov(s,obj) for name,obj in {**case,'display':refs['panel'],'battery':refs['battery_envelope']}.items()}
 for n,v in tests.items():
  if v>1e-6:nonzero.append({'ref':ref,'other':n,'mm3':v})
 rows.append({'ref':ref,'height_budget_mm':by[ref]['height_budget_mm'],'height_basis':by[ref]['height_basis'],'intersections_mm3':tests,'body_geometry':inspect(s)})
pairs=[]
for (an,a),(bn,b) in itertools.combinations(bodies.items(),2):
 v=ov(a,b)
 if v>1e-6:pairs.append({'a':an,'b':bn,'mm3':v})
reserved=[];intentional=[]
for space in ('wire_keepout','ph_plug_keepout','flex_keepout'):
 for ref,s in bodies.items():
  v=ov(s,refs[space])
  if v>1e-6:
   row={'space':space,'ref':ref,'mm3':v}
   if (space=='ph_plug_keepout' and ref=='J2') or (space=='flex_keepout' and ref=='J1'):intentional.append(row)
   else:reserved.append(row)
posts=[]
for p in coverage['parts']:
 for r in M.SUPPORTS:
  a=area(p['xy_envelope_front_rect_mm'],r)
  if a>1e-8:posts.append({'ref':p['ref'],'rect':r,'area_mm2':a})
service=[]
for b in M.E['service_buttons']:
 ref=b['ref'];x,y=b['x'],b['y'];p=by[ref]
 probe=M.cylinder(x,-y,M.BACK-.1,-p['height_budget_mm'],1.2)
 hits={n:ov(probe,s) for n,s in {**case,**{n:s for n,s in bodies.items() if n!=ref}}.items()}
 pos=max(abs(x-p['position_mm'][0]),abs(y-p['position_mm'][1]))
 service.append({'ref':ref,'position_error_mm':pos,'positive_hits':{n:v for n,v in hits.items() if v>1e-6}})
actual=cq.importers.importStep(str(O/'pcb_actual_export.step')).val().translate((0,0,T['raw_to_mechanical_z']))
actualchecks={n:ov(actual,s) for n,s in {**case,'display':refs['panel'],'battery':refs['battery_envelope']}.items()}
# Check both derived-export pose and manufacturer nominal board-face pose.
nominal_usb=refs['usb_outline'].translate((0,0,.040))
usb_nominal={n:ov(nominal_usb,s) for n,s in {**case,'display':refs['panel'],'battery':refs['battery_envelope']}.items()}
button={'rest_gap_to_nominal_2p5_switch_mm':-2.5-M.E['update_button']['tip_z'],'rest_gap_with_0p1_mount_budget_mm':-2.6-M.E['update_button']['tip_z'],'rest_gap_to_max_2p8_envelope_mm':-2.8-M.E['update_button']['tip_z'],'measured_gap_mm':None,'accepted_measured_gap_mm':[.10,.20],'max_travel_mm':.25,'engineering_overtravel_margin_mm':.05,'nominal_stop_travel_mm':M.E['update_button']['hard_stop_travel'],'accepted_gap_plus_stroke_plus_margin_mm':.20+.25+.05,'requires_measurement':True,'limit':'Positive measured rest gap and measured stop >= gap + max stroke + margin required; safe switch overtravel/force/fatigue unqualified.'}
assert button['accepted_gap_plus_stroke_plus_margin_mm']<=button['nominal_stop_travel_mm']
fail=bool(nonzero or pairs or reserved or posts or any(s['positive_hits'] or s['position_error_mm']>1e-6 for s in service) or max(actualchecks.values())>1e-6 or max(usb_nominal.values())>1e-6)
write('populated_proxy_validation.json',{'status':'REVIEW_REQUIRED_RESERVED_SPACE_CONFLICTS' if fail else 'PASS_CHECKED_NOMINAL_ENVELOPES_ONLY','component_count':81,'all_per_reference_results':rows,'proxy_positive_intersections':nonzero,'component_pair_positive_intersections':pairs,'reserved_space_positive_intersections':reserved,'intentional_mating_reserve_overlaps':intentional,'support_courtyard_hits':posts,'service_port_checks':service,'update_button':button,'actual_partial_step':{'geometry':inspect(actual),'intersections_mm3':actualchecks,'source_sha256':K.digest(O/'pcb_actual_export.step')},'nominal_source_USB_pose_intersections_mm3':usb_nominal,'model_coverage':{'added_refs':coverage['added_refs'],'missing_referenced_count':len(coverage['missing_referenced_refs']),'no_model_refs':coverage['unmodeled_refs']},'open_physical_gates':K.OPEN_GATES})
materials={n:refs[k] for n,k,cat in K.OBJECTS if cat=='materials'}
materialhits=[]
for n,s in materials.items():
 for other,o in {**case,'panel':refs['panel'],'pcb':refs['pcb_placeholder'],'battery':refs['battery_envelope'],**bodies}.items():
  v=ov(s,o)
  if v>1e-6:materialhits.append({'a':n,'b':other,'mm3':v})
for (a,s),(b,o) in itertools.combinations(materials.items(),2):
 v=ov(s,o)
 if v>1e-6:materialhits.append({'a':a,'b':b,'mm3':v})
aahits=[]
for n,r in {**T['strips'],**T['shoulders']}.items():
 if area(r,T['aa_no_press_rect'])>1e-8:aahits.append(n)
frontrows=[{'name':n,'nominal_face_gap_mm':T['front_seat_z']-T['front_psa_t']-T['front_foam_t']-(M.PANEL_BOTTOM+M.P['t']),'max_local_panel_gap_mm':T['front_seat_z']-T['front_psa_t']-T['front_foam_t']-(M.PANEL_BOTTOM+T['panel_upper_max_t'])} for n in T['strips']]
rearrows=[{'name':'RearFoam_'+str(i),'free_foam_t_mm':T['rear_foam_free_t'],'installed_foam_t_mm':T['rear_foam_installed_t'],'compression_ratio':1-T['rear_foam_installed_t']/T['rear_foam_free_t'],'stack_bottom_z_mm':T['rear_post_top_z'],'stack_top_z_mm':0} for i in range(1,5)]
audit={n:ov(s,refs['panel_global_audit']) for n,s in materials.items() if n.startswith('Front')}
clampfail=bool(materialhits or aahits or any(r['max_local_panel_gap_mm']<=0 for r in frontrows))
write('clamping_validation.json',{'status':'FAIL_NOMINAL_C1_GEOMETRY' if clampfail else 'PASS_NOMINAL_C1_GEOMETRY_ONLY','material_shape_names':list(materials),'aa_no_press_projection_hits':aahits,'positive_intersections':materialhits,'front_pad_rows':frontrows,'rear_pad_rows':rearrows,'global_1p2_audit_overlap_mm3':audit,'global_audit_note':'Full1.2 audit retained. Positive overlap here is explicit conservative audit conflict; local0.85 upper-envelope model needs vendor holding-region approval.','lateral_capture':{'nominal_guide_width_mm':58.2,'nominal_board_width_mm':58,'nominal_half_play_mm':.1,'measured_half_play_mm':None,'limit':'Measure edge excursion including yaw at all shoulder and glass corner stations; midpoint translation is insufficient.'},'tolerance_stack':{'example_front_gap_mm':frontrows[0]['max_local_panel_gap_mm']-.10-.05,'verified_worst_case':False,'local_bearing_height_measured':False},'measurement_acceptance':{'front_gap_min_mm':.10,'front_gap_max_mm':.25,'rear_compression_min':.20,'rear_compression_max':.30},'manufacturing_release_blocked':True,'open_physical_gates':K.OPEN_GATES})
# Conservative pad/mask and all-via projection audit, plus actual exported copper.
inputs=json.loads((V/'pcb_contact_inputs.json').read_text());assert inputs['board_sha256']==K.BOARD_SHA
contacthits=[];contactrows=[]
copper=cq.importers.importStep(str(O/'pcb_copper_audit.step')).val().translate((0,0,T['raw_to_mechanical_z']))
contacts=[('Shoulder_'+n,r,'front') for n,r in T['shoulders'].items()]+[('RearFoam_'+str(i),r,'back') for i,r in enumerate(M.SUPPORTS,1)]
for n,r,side in contacts:
 hit=[]
 for p in inputs['pads']:
  if (p[side+'_mask'] or max(p['drill_mm'])>0) and area(r,p['mask_bbox'])>1e-8:hit.append({'ref':p['ref'],'pad':p['number']})
 for i,v in enumerate(inputs['vias']):
  if area(r,v['bbox'])>1e-8:hit.append({'via':i})
 if hit:contacthits.append({'contact':n,'hits':hit})
 z0,z1=(.755,.790) if side=='front' else (.010,.045)
 column=front_box(r,z0,z1);coppervolume=ov(column,copper)
 contactrows.append({'name':n,'side':side,'rect':r,'masked_copper_projection_area_estimate_mm2':coppervolume/(z1-z0),'bearing_datum':'Nominal full-stack plane only; etched-Cu step, mask conformality and local finished thickness must be measured','nominal_etched_copper_height_difference_mm':.035,'local_surface_height_verified':False})
write('pcb_contact_audit.json',{'status':'FAIL_CONTACT_PROJECTION' if contacthits else 'PASS_CONSERVATIVE_CONTACT_PROJECTIONS_ONLY','contact_rows':contactrows,'exposed_pad_or_via_hits':contacthits,'input_sha256':K.digest(V/'pcb_contact_inputs.json'),'copper_step_sha256':K.digest(O/'pcb_copper_audit.step'),'limits':['Conservative mask-expanded pad boxes and every via annulus excluded. Masked copper under soft pads is recorded, not automatically wear-qualified.','No blind0.035mm stop shift: measure local bearing datum, then select shims/stop depths; PCB uniform0.8 envelope is not proof of contact height.']})
# Actual section: Boolean slice of current physical/reference solids. Z displayed5x.
assembly=cq.Assembly(name='C1_ALL_REFERENCE_ENVELOPES')
items={**case,'panel':refs['panel'],'pcb_core':refs['pcb_actual_core'],'battery':refs['battery_envelope'],**materials,**{'Envelope_'+n:s for n,s in bodies.items()}}
for n,s in items.items():assembly.add(s,name=n)
assembly.save(str(O/'portrait_assembly_with_envelopes.step'))
slab=M.box(26.94,-101,-8,27.24,10,5);scale=cq.Matrix([[1,0,0,0],[0,1,0,0],[0,0,5,0],[0,0,0,1]])
colors={'front_frame':'#344554','back_cover':'#8192a0','panel':'#e6d7a8','pcb_core':'#367e63','battery':'#adb8c3'}
sections=[]
for n,s in items.items():
 cut=s.intersect(slab)
 if cut.Volume()>1e-8:sections.append((cut.transformGeometry(scale),colors.get(n,'#d79356' if n in materials else '#566674')))
render_shapes(sections,O/'portrait_actual_section.png','C1 actual Boolean section X=27.09 | thickness axis5x | not physical fit',elevation=0,azimuth=0)
render_shapes([(refs['pcb_actual_core'],'#367e63'),(refs['battery_envelope'],'#adb8c3')]+[(s,'#566674') for s in bodies.values()],O/'portrait_internal_envelopes.png','C1 actual board core +81 sourced/height envelopes | physical gates open',elevation=-60,azimuth=65)
stack=[{'layer':'front_bezel','z_mm':[2.3,3.5]},{'layer':'front_PSA_local','z_mm':[2.39,2.45]},{'layer':'front_foam_local','z_mm':[1.89,2.39]},{'layer':'display_upper_max','z_mm':[.93,1.78]},{'layer':'display_local_bottom_max','z_mm':[.93,2.13]},{'layer':'screen_PSA_non_AA','z_mm':[.8,.93]},{'layer':'finished_PCB_budget','z_mm':[0,.8]},{'layer':'KiCad_core_mapped','z_mm':[.045,.755]},{'layer':'rear_foam','z_mm':[-.60,0]},{'layer':'rear_foam_PSA','z_mm':[-.65,-.60]},{'layer':'rear_PET','z_mm':[-.80,-.65]},{'layer':'rear_post_PSA','z_mm':[-.85,-.80]},{'layer':'battery_envelope','z_mm':[-5.7,-.1]},{'layer':'rear_cavity','z_mm':[-6.2,0]},{'layer':'rear_cover','z_mm':[-7.6,-6.2]}]
write('internal_envelope_validation.json',{'status':'REVIEW_REQUIRED_INTERNAL_ASSEMBLY' if fail else ('FAIL_NOMINAL_INTERNAL' if clampfail else 'PASS_NOMINAL_STACK_AND_SECTION_ONLY'),'layer_stack_front_to_back':stack,'total_mm':11.1,'section':{'plane_x_mm':27.09,'slab_thickness_mm':.3,'z_display_scale':5},'battery_actual_envelope_thickness_mm':inspect(refs['battery_envelope'])['bbox_mm'][2],'intentional_zero_distance_contacts':['Screen PSA0.8..0.93 bonds nominal PCB and display back','Rear two PSAs+PET+compressed foam end at nominal PCBback0','Shoulders are nominal axial stops; local mask/etched edge bearing height must be measured'],'critical_open_items':K.OPEN_GATES})
from PIL import Image,ImageDraw,ImageFont
im=Image.new('RGB',(1420,1320),'#f0f4f7');d=ImageDraw.Draw(im);font='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
f=lambda n:ImageFont.truetype(font,n)
d.text((50,35),'C1 一体工牌：实际分层预算 / 66×109×11.1 mm',font=f(34),fill='#203749')
for i,row in enumerate(stack):
 z=row['z_mm'];d.text((60,105+i*62),row['layer'],font=f(23),fill='#344f61');d.text((600,105+i*62),f'Z {z[0]:+.3f} 至 {z[1]:+.3f} mm',font=f(23),fill='#344f61')
d.text((60,1090),'前软垫名义间隙0.18；上部最大屏厚时0.11 mm。并非全公差无压保证。',font=f(23),fill='#a3633c')
d.text((60,1140),'首件测量选垫：前间隙0.10–0.25；后泡棉压缩20–30%。',font=f(23),fill='#344f61')
d.text((60,1190),'蚀刻边缘承压高度、玻璃夹持许可、FPC、导线、按键寿命、RF仍待验证。',font=f(23),fill='#344f61')
im.save(O/'portrait_layer_stack.png')
assert not nonzero and not posts and max(actualchecks.values())<1e-6 and max(usb_nominal.values())<1e-6,('SOLID_CONFLICT',nonzero,posts,actualchecks)
assert all(not q['positive_hits'] and q['position_error_mm']<1e-6 for q in service)
assert all(set((q['a'],q['b']))=={'TP2','TP3'} for q in pairs),pairs
assert {(q['space'],q['ref']) for q in reserved}=={('ph_plug_keepout','SW3'),('flex_keepout','C118'),('flex_keepout','C119'),('flex_keepout','C120'),('flex_keepout','C121')},reserved
pads={p['ref']:p for p in inputs['pads'] if p['ref'] in ('TP2','TP3')}
assert set(pads)=={'TP2','TP3'} and area(pads['TP2']['bbox'],pads['TP3']['bbox'])==0
write('assembly_review_gates.json',{'status':'REVIEW_REQUIRED_ASSEMBLY','manufacturing_release_blocked':True,'retained_courtyard_pair_intersections':pairs,'test_pad_refinement':{'pad_bbox_overlap_mm2':0,'source':'KiCad10 actual copper pad bounding boxes; no fitted testpoint pins','original_courtyard_shapes_retained':True},'blocking_reserved_conflicts':reserved,'geometry_changed_to_hide_conflicts':False,'required_actions':['PH/SW3: obtain exact mounted PHR2/lead exit and switch body geometry, prove clearance or revise mechanical mating path/PCB through a new electrical revision.','FPC/C118..C121: original full-block reserve retained; prove source-backed folded route and connector lock access or revise layout through a new electrical revision.','Do not order or force assembly based on clear outer shell or zero local material interference.']})
assert not clampfail,('CLAMP',materialhits,aahits)
assert not contacthits,('CONTACT',contacthits)
print('C1 CHECKS EXECUTED: REVIEW_REQUIRED_ASSEMBLY; retained PH/FPC blockers; no manufacturing release')
