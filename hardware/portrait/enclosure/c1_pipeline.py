"""Visible C1 source setup, sequential checks, then GUI-proof finalization.
Run --setup once, --run, execute OpenC1RevisionB.FCMacro in GUI, then --finalize.
All final outputs are explicit producer declarations, not a directory glob.
"""
from pathlib import Path
import sys,json,subprocess,datetime,shutil,hashlib,py_compile
import c1_config as K
H=Path(__file__).resolve().parent;R=H.parents[2];V=H/'validation';O=H/'output';sha=K.digest
stamp=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
pins=json.loads((V/'eda_frozen_inputs.json').read_text())
assert all(sha(R/p)==h for p,h in pins.items())
mode=sys.argv[1]
if mode=='--setup':
 backup=V/'legacy_before_c1_final';backup.mkdir(exist_ok=True)
 for name,target in [('export_freecad.py','c1_export_native.py'),('validate_populated.py','c1_validate.py'),('inspect_internal.py','c1_validate.py')]:
  p=H/name
  if not (backup/name).exists():shutil.copy2(p,backup/name)
  p.write_text('"""C1 entry; legacy source archived in validation/legacy_before_c1_final."""\nfrom pathlib import Path\nimport runpy\nrunpy.run_path(str(Path(__file__).with_name('+repr(target)+')),run_name="__main__")\n')
 p=H/'render_review.py';s=p.read_text()
 if 'UPDATE / C1' not in s:
  shutil.copy2(p,backup/p.name)
  s=s.replace('CHROMA  /  P1.1 REV B','CHROMA  /  P1.1 REV B C1')
  anchor="  d.text((bx+W/2,by+H-37),'PCB 当前布局示意 · 不是实装照片'"
  assert s.count(anchor)==1
  insert="  ub=E['update_button'];q=xy(M.BW-ub['x'],ub['y']);d.rounded_rectangle((q[0]-13,q[1]-14,q[0]+13,q[1]+14),radius=5,fill='#66757f',outline='#e4edf2',width=2);d.text((q[0]-18,q[1]-5),'UPDATE / C1',font=f(11),fill='#edf3f5',anchor='rm')\n"
  s=s.replace(anchor,insert+anchor).replace('5.2*S','7.5*S');p.write_text(s)
 for p in H.glob('*.py'):py_compile.compile(str(p),doraise=True)
 for p in H.glob('*.FCMacro'):compile(p.read_text(),str(p),'exec')
 print('SETUP COMPILED; frozen EDA unchanged')
 sys.exit(0)
def inputs():
 ps=set(H.glob('*.py'))|set(H.glob('*.FCMacro'))|{R/p for p in pins}
 ps|={p for p in (R/'hardware/portrait/pcb/lib').rglob('*') if p.is_file() and p.suffix.lower() in ('.step','.stp','.kicad_mod')}
 ps|={p for p in (H/'sources').glob('*') if p.is_file()}
 ps|={V/n for n in ('pcb_model_coverage.json','pcb_contact_inputs.json','stackup_gui_observed.txt')}
 ps|={O/n for n in ('pcb_actual_export.step','pcb_board_body.step','pcb_copper_audit.step')}
 return {str(p.relative_to(R)):sha(p) for p in sorted(ps)}
def rel(p):return str(p.relative_to(R))
build_outputs=[O/('portrait_'+k+e) for k in ('front_frame','back_cover') for e in ('.step','.stl')]
build_outputs += [O/('reference_'+key+'.step') for n,key,cat in K.OBJECTS if cat!='structure']
build_outputs += [O/n for n in ('portrait_assembly.step','mechanical_dimensions.json','portrait_iso_front.png','portrait_exploded.png')]+[V/n for n in ('mechanical_expectation.json','c1_reference_geometry.json','mechanical_validation.json')]
stages=[
 ('build',['cadquery-python',str(H/'build_enclosure.py')],build_outputs),
 ('native',['freecad-python',str(H/'export_freecad.py')],[O/'portrait_assembly_revisionB.FCStd',V/'freecad_readback.json',V/'pcb_step_frame.json']),
 ('geometry',['cadquery-python',str(H/'validate_populated.py')],[V/n for n in ('populated_proxy_validation.json','clamping_validation.json','pcb_contact_audit.json','internal_envelope_validation.json','assembly_review_gates.json')]+[O/n for n in ('portrait_assembly_with_envelopes.step','portrait_actual_section.png','portrait_internal_envelopes.png','portrait_layer_stack.png')]),
 ('access',['cadquery-python',str(H/'validate_access_spaces.py')],[V/'access_space_validation.json']),
 ('exports',['cadquery-python',str(H/'validate_exports.py')],[V/'export_validation.json']),
 ('layout',['freecad-python',str(H/'export_layout_preview.py')],[V/'layout_preview_source.json']+[O/n for n in ('pcb_back_layout.svg','pcb_edge_crop.svg','pcb_back_layout_clipped.svg','pcb_back_layout_clipped.png')]),
 ('review',['cadquery-python',str(H/'render_review.py')],[O/'portrait_review_overview.png',O/'portrait_screen_demo_400x600.png'])]
pending=V/'c1_pipeline_pending.json'
if mode=='--run':
 before=inputs();record={'started_utc':stamp(),'input_before':before,'stages':[],'exit_code':None}
 pending.write_text(json.dumps(record,indent=2)+'\n')
 for name,cmd,declared in stages:
  print('RUN',name,cmd,flush=True)
  log=V/('c1_final_'+name+'.log')
  with log.open('w') as f:
   p=subprocess.Popen(cmd,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   for line in p.stdout:print(line,end='',flush=True);f.write(line);f.flush()
   code=p.wait()
  stage={'name':name,'command':cmd,'exit_code':code,'log':rel(log),'declared_outputs':[rel(p) for p in declared],'outputs':{rel(p):sha(p) for p in declared if p.exists()}}
  record['stages'].append(stage);record['input_after']=inputs();record['finished_utc']=stamp();record['exit_code']=code
  pending.write_text(json.dumps(record,indent=2)+'\n')
  assert before==record['input_after'],'Inputs changed during pipeline'
  assert code==0,(name,code)
  assert all(p.exists() for p in declared)
 print('ALL DECLARED C1 COMMANDS EXIT0; NEXT: ACTUAL FREECAD GUI SAVE/REOPEN MACRO')
elif mode=='--finalize':
 record=json.loads(pending.read_text());assert len(record['stages'])==len(stages) and all(s['exit_code']==0 for s in record['stages'])
 assert record['input_before']==record['input_after']==inputs()
 gui=json.loads((V/'native_gui_readback.json').read_text());native=O/gui['native_file']
 assert gui['reopened'] and gui['native_sha256']==sha(native)
 plan=json.loads((V/'mechanical_expectation.json').read_text());assert set(gui['parts'])==set(plan['expected_shape_names'])
 outputs={}
 for s in record['stages']:
  for name,h in s['outputs'].items():
   if name!=rel(native):assert sha(R/name)==h,('Changed produced artifact',name)
   outputs[name]=sha(R/name)
 # These were imported and independently checked, not generated by this pipeline.
 verified=[O/'pcb_actual_export.step',O/'pcb_board_body.step',O/'pcb_copper_audit.step',V/'pcb_model_coverage.json',V/'pcb_contact_inputs.json',V/'stackup_gui_observed.txt']
 record['independently_revalidated_input_artifacts']={rel(p):sha(p) for p in verified}
 outputs.update(record['independently_revalidated_input_artifacts'])
 for p in [V/'native_gui_readback.json']+[O/n for n in ('portrait_native_C1_iso.png','portrait_native_C1_front.png','portrait_native_C1_internal.png')]:outputs[rel(p)]=sha(p)
 record.update(exit_code=0,outputs=outputs,native_gui_producer='OpenC1RevisionB.FCMacro',native_gui_sha256=sha(native),finished_utc=stamp(),status='EXECUTED_REVIEW_REQUIRED_C1_PIPELINE',manufacturing_release_blocked=True)
 (V/'execution-provenance.json').write_text(json.dumps(record,indent=2)+'\n')
 print('FINAL C1 PROVENANCE',len(outputs),'explicit produced/revalidated artifacts; physical gates OPEN')
else:raise SystemExit('Use --setup, --run, --finalize')
assert all(sha(R/p)==h for p,h in pins.items())
