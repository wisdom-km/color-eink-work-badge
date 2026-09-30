#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Visible, source-only P36 review freeze and deterministic ZIP. Never routes or saves CAD.
Run freeze in a visible terminal; it streams real software tests before binding hashes.
Review-required geometry is retained. No manufacturing release or flash binary export.
"""
from pathlib import Path, PurePosixPath
from collections import Counter
import argparse, csv, datetime, hashlib, json, re, subprocess, sys, zipfile
import xml.etree.ElementTree as ET
P='hardware/portrait/pcb/'
E='hardware/portrait/enclosure/'
V=E+'validation/'
O=E+'output/'
A='verification/visible-final/'
S='hardware/portrait/verification/visible-final/'
BOARD=P+'badge.kicad_pcb'
BASE='hardware/pcb/scripts/design.py'
NATIVE=O+'portrait_assembly_revisionB.FCStd'
EXCLUDED_IMAGE=O+'portrait_review_overview.png'
SCRIPT='tools/portrait_environment/package_review_zip.py'
EDA_REPORTS='erc.json erc.rpt drc.json drc.rpt netlist.xml net-parity.json result.json source-before.json source-after.json execution-sha-log.json cleanup-result.json schematic-review.pdf warning-review.json'.split()
CAD_REPORTS='mechanical_expectation.json execution-provenance.json native_gui_readback.json mechanical_validation.json export_validation.json internal_envelope_validation.json access_space_validation.json usb_envelope_source.json pcb_model_coverage.json pcb_step_frame.json populated_proxy_validation.json freecad_readback.json layout_preview_source.json clamping_validation.json pcb_contact_audit.json pcb_contact_inputs.json assembly_review_gates.json c1_reference_geometry.json stackup_gui_observed.txt eda_frozen_inputs.json'.split()
VENDOR_SHA='5a6b79434963dade51244d4ec7cb16fc6cc35b31703073b32b186792ac58fcca'

def need(ok,msg):
    if not ok: raise SystemExit('STOP: '+str(msg))
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(b): return hashlib.sha256(b).hexdigest()
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()
def allowed(n):
    p=PurePosixPath(n)
    if p.is_absolute() or '..' in p.parts: return False
    for part in p.parts:
        if part in {'.git','.pio','__pycache__','.history','.cursor','smoke-state','legacy_before_c1_final','pre_antenna_fix'}: return False
        if part.startswith(('before_','before-','superseded_','backup-','integration-backup-','integration-check-','review_classification_')): return False
        if part.endswith(('_backup','_backups','-backup','-backups')): return False
    if p.name in {'phone_mock_server.py','host-suite-exit.txt','platformio-build-exit.txt','portrait_assembly.FCStd','freecad_readback_revisionA.json'}: return False
    if '.before_' in p.name or p.name.startswith('.env'): return False
    return p.suffix.lower() not in {'.pyc','.lck','.kicad_prl','.fcbak','.fcstd1','.pem','.key','.p12','.pfx','.elf','.a','.o','.jar','.exe'}
def path(n):
    p=R/n
    need(allowed(n) and p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(R),'Unsafe/missing file '+n)
    return p
def J(n): return json.loads(path(n).read_text())
def snap(ns): return {n:sha(path(n)) for n in sorted(ns)}
def same(m):
    need(isinstance(m,dict) and bool(m),'Missing hash map')
    for n,h in m.items(): need(sha(path(n))==h,'SHA mismatch '+n)
def names(folder,extensions,recursive=True):
    root=R/folder
    need(root.is_dir(),'Missing directory '+folder)
    it=root.rglob('*') if recursive else root.glob('*')
    return {p.relative_to(R).as_posix() for p in it if p.is_file() and p.suffix.lower() in extensions and allowed(p.relative_to(R).as_posix())}
def sheets():
    ns=re.findall(r'\(property\s+"Sheetfile"\s+"([^"]+)"',path(P+'badge.kicad_sch').read_text())
    need(len(ns)==4 and len(set(ns))==4 and all('/' not in n and n.endswith('.kicad_sch') for n in ns),'Expected master plus four child sheets')
    return {P+'badge.kicad_sch'}|{P+n for n in ns}
def software_inputs():
    ns=names('firmware/portrait36',{'.cpp','.h','.ini'})
    ns|={'firmware/include/portrait_frame.h','firmware/src/portrait_frame.cpp','tools/portrait_environment/env.sh'}
    for folder in ['tools/portrait_display','tools/portrait_driver']:
        ns|=names(folder,{'.py','.cpp','.h','.sh'},False)
    ns|=names('tools/portrait_display/phone',{'.html','.js'})
    ns|=names('tools/portrait_driver/phone',{'.cpp','.h'})|names('tools/portrait_driver/arduino_stub',{'.h'})
    ns|={'tools/portrait_display/output/preview400x600/'+n for n in ['manifest.json','portrait.rgba','panel-3in6e-native.bin']}
    return ns

def producer(prov):
    need(prov['status']=='EXECUTED_REVIEW_REQUIRED_C1_PIPELINE' and prov['exit_code']==0 and prov['manufacturing_release_blocked'] is True,'CAD pipeline review state')
    need(prov['input_before']==prov['input_after'],'CAD input changes')
    same(prov['input_after']); same(prov['outputs'])
    need([x['name'] for x in prov['stages']]==['build','native','geometry','access','exports','layout','review'],'CAD stages')
    produced={}; logs=set()
    for st in prov['stages']:
        need(st['exit_code']==0 and st['command'],'Stage incomplete '+st['name'])
        need(len(st['declared_outputs'])==len(set(st['declared_outputs'])) and set(st['declared_outputs'])==set(st['outputs']),'Producer declaration mismatch')
        need(not (set(produced)&set(st['outputs'])),'Duplicate producer')
        produced.update(st['outputs']); logs.add(st['log']); path(st['log'])
    independent=prov['independently_revalidated_input_artifacts']
    need(set(independent)=={O+n for n in ['pcb_actual_export.step','pcb_board_body.step','pcb_copper_audit.step']}|{V+n for n in ['pcb_model_coverage.json','pcb_contact_inputs.json','stackup_gui_observed.txt']},'Independent artifact list')
    need(all(prov['input_before'].get(n)==h for n,h in independent.items()),'Imported artifact lacks before hash')
    gui={V+'native_gui_readback.json'}|{O+'portrait_native_C1_'+n+'.png' for n in ['iso','front','internal']}
    need(set(prov['outputs'])==set(produced)|set(independent)|gui,'Final output ledger mismatch')
    for n,h in produced.items():
        if n!=NATIVE: need(prov['outputs'][n]==h,'Stage/final mismatch '+n)
    # Root specifically excluded this misleading image from delivery, not from history validation.
    need(EXCLUDED_IMAGE in produced,'Excluded historical image no longer declared')
    return logs,produced

def catalog(audit_files):
    prov=J(V+'execution-provenance.json');logs,_=producer(prov)
    ns={'LICENSE.md','README.md','AGENTS.md','THIRD_PARTY_NOTICES.md',SCRIPT,BOARD,P+'badge.kicad_pro',P+'candidate_bom.csv',P+'fp-lib-table',P+'sym-lib-table',P+'README.md'}|sheets()
    ns|=names('LICENSES',{'.md','.txt'})|names('docs/portrait',{'.md','.txt','.json','.csv','.pdf','.xlsx'})
    ns|=names('hardware/pcb/scripts',{'.py','.sh'})|names(P+'scripts',{'.py','.sh'})
    ns|=names(P+'lib',{'.md','.txt','.kicad_sym','.kicad_mod','.step','.stp'})
    ns|=names('hardware/portrait/references',{'.pdf','.txt'})
    ns|=names(E,{'.py','.fcmacro','.md'},False)|names(E+'assets',{'.png'})|names(E+'sources',{'.pdf','.md','.json','.txt'})
    ns|=(set(prov['outputs'])-{EXCLUDED_IMAGE})|logs|{V+n for n in CAD_REPORTS}|{V+'pcb_snapshot/source_board.sha256'}
    ns|={A+n for n in EDA_REPORTS}|names(S,{'.json','.log','.rpt','.sha256','.txt'})
    ns|=software_inputs()|names('firmware/portrait36',{'.md'})
    for d in ['tools/portrait_display','tools/portrait_driver']:
        ns|=names(d,{'.md','.txt'},False)
    ns|=names('tools/portrait_display/phone',{'.md'})
    ns|={'tools/portrait_driver/vendor-oracle.json'}
    ns|={'tools/portrait_display/output/preview400x600/'+n for n in ['portrait.png','portrait-2x.png']}
    ns|={'tools/portrait_environment/'+n for n in ['env.sh','README.md','download-provenance.json','platformio-packages.json','platformio-python-requirements.txt','kicad-appimage-sha256.txt']}
    ns|={'tools/portrait_environment/freerouting-offline/'+n for n in ['README.md','FREEROUTING-GPL-LICENSE.txt','local-only.patch','apply_offline_patch.py','verify_offline_source.py','package_overlay.py','rebuild_overlay.sh','artifact-manifest.json','static-verification.json','bytecode-noop-verification.json','modified-source-sha256.json']}
    ns|=set(audit_files)
    for n in ns: path(n)
    need(EXCLUDED_IMAGE not in ns,'Excluded image selected')
    required=set(prov['input_after'])|set(J(A+'source-after.json'))|set(J(V+'mechanical_expectation.json')['source_sha256'])|software_inputs()
    need(required<=ns,'Unpackaged dependency '+str(sorted(required-ns)))
    return sorted(ns)

def electrical():
    after=J(A+'source-after.json');same(after)
    need(after==J(A+'source-before.json'),'EDA audit input change')
    result=J(A+'result.json');board=sha(path(BOARD))
    need(result['board_before']==result['board_after']==board and result['source_after']==after,'Board/source report mismatch')
    need(result['board_counts']=={'footprint':81,'segment':968,'via':115,'zone':10},'Board counts')
    need(sheets()<=set(after),'Missing sheet hash')
    for record in J(A+'execution-sha-log.json'):
        need(record['returncode']==0 and record['before']==record['after']==after,'EDA command/hash mismatch')
    net=J(A+'net-parity.json');need(net['parts']==81 and net['connected_pins']==259 and net['nc_pins']==28 and not net['errors'],'Net parity')
    drc=J(A+'drc.json');erc=J(A+'erc.json')
    need(drc['kicad_version']==erc['kicad_version']=='10.0.6','KiCad version')
    need(not drc['violations'] and not drc['schematic_parity'] and not drc['unconnected_items'] and not drc['ignored_checks'],'DRC/ignored findings')
    need({'error','warning'}<=set(drc['included_severities']) and not erc['ignored_checks'],'Severity coverage')
    project=J(P+'badge.kicad_pro')
    need(not project['board']['design_settings'].get('drc_exclusions',[]) and not project['erc'].get('erc_exclusions',[]),'Project exclusions')
    need('ignore' not in project['erc'].get('rule_severities',{}).values(),'Ignored ERC rule')
    records=[]
    for sheet in erc['sheets']:
        for violation in sheet['violations']:
            need(violation['severity']=='warning' and violation['type']=='single_global_label','Unreviewed ERC category')
            records.append({'sheet_path':sheet['path'],'sheet_uuid_path':sheet['uuid_path'],'violation':violation})
    review=J(A+'warning-review.json')
    need(review['erc_report_sha256']==sha(path(A+'erc.json')) and review['netlist_sha256']==sha(path(A+'netlist.xml')) and review['board_sha256']==board and review['input_sha256']==after,'Warning review binding')
    need(str(review['gui_review']).startswith('Completed') and not review['ignored_checks'],'GUI/ignored review')
    need(len(records)==len(review['warnings'])==9,'Warning cardinality')
    need(Counter(digest(canonical(x)) for x in records)==Counter(x['fingerprint_sha256'] for x in review['warnings']),'Warning fingerprints')
    need({x['net_name'] for x in review['warnings']}=={'CC1','CC2','PROG','LED_CHRG_A','CHRG_STAT','SW_H','PUMP_H','SW_C','EPD_SUPPLY'},'Warning net names')
    xml=ET.parse(path(A+'netlist.xml')).getroot()
    for w in review['warnings']:
        need(w['reason'] and digest(canonical({k:w[k] for k in ['sheet_path','sheet_uuid_path','violation']}))==w['fingerprint_sha256'],'Missing warning rationale/fingerprint')
        actual=[dict(node.attrib) for net in xml.findall('./nets/net') if net.get('name')==w['net_name'] for node in net.findall('node')]
        need(len(actual)>=2 and Counter(canonical(x) for x in actual)==Counter(canonical(x) for x in w['actual_netlist_nodes']),'Wired warning endpoints')
    return board,after

def mechanical(board, reviewed_sha):
    prov=J(V+'execution-provenance.json');logs,produced=producer(prov)
    plan=J(V+'mechanical_expectation.json');same(plan['source_sha256'])
    sources=names(E,{'.py','.fcmacro'},False)
    need(set(plan['source_sha256'])==sources,'Expectation source set')
    need(plan['board_sha256']==board and plan['base_design_sha256']==sha(path(BASE)) and plan['c1_config_sha256']==sha(path(E+'c1_config.py')),'C1 source/board binding')
    need(plan['design_revision']=='P1.1-revisionB-C1' and plan['minimum_reference_count']==81,'Revision/reference minimum')
    meta={k:plan[k] for k in ['design_revision','base_design_sha256','c1_config_sha256','config_sha256','board_sha256']}
    for name in ['mechanical_validation.json','populated_proxy_validation.json','freecad_readback.json','clamping_validation.json','pcb_contact_audit.json','assembly_review_gates.json','pcb_step_frame.json']:
        d=J(V+name);need(all(d.get(k)==v for k,v in meta.items()),'Mechanical metadata '+name)
    dimensions=J(O+'mechanical_dimensions.json')
    need(all(dimensions['derived'].get(k)==v for k,v in meta.items()),'Dimensions metadata')
    need(digest(json.dumps(dimensions['canonical'],sort_keys=True).encode())==plan['config_sha256'],'Merged config SHA')
    need(J(V+'layout_preview_source.json')['board_sha256']==board,'Layout source')
    same(J(V+'eda_frozen_inputs.json'))
    coverage=J(V+'pcb_model_coverage.json');refs={x['ref'] for x in coverage['parts']}
    need(coverage['footprint_count']==len(coverage['parts'])==len(refs)==81 and coverage['board_sha256']==board,'81 footprint coverage')
    need('10.0.6' in coverage['kicad_python_version'],'KiCad coverage version')
    full=sha(path(O+'pcb_actual_export.step'));bare=sha(path(O+'pcb_board_body.step'))
    need(coverage['full_step_sha256']==full and coverage['bare_step_sha256']==bare,'Raw STEP coverage')
    frame=J(V+'pcb_step_frame.json')
    need(frame['status']=='PASS_RAW_EXPORT_FRAME_ONLY' and not frame['failures'] and frame['raw_step_sha256']==full and frame['bare_step_sha256']==bare,'Raw STEP frame')
    expected_refs={r:('USB_HRO_Body_Envelope' if r=='J3' else 'Envelope_'+r) for r in refs}
    need(plan['reference_shape_names']==expected_refs,'Independent ref-to-shape mapping')
    base_names=['FrontFrame','BackCover','Display_Local_Max_Envelope','PCB_0p8_Envelope','PCB_KiCad_Core_In_Mechanical_Frame','Battery_Adafruit1578_Envelope','USB_HRO_Body_Envelope','Lead_Clearance_Reserve','PH_Plug_Clearance_Reserve','Display_Global_1p2_Audit','AA_NoPress_Audit']
    materials=[p+'_'+side for side in ['Left','Right','Top'] for p in ['ScreenPSA','FrontFoam','FrontPSA']]+[p+'_'+str(i) for i in range(1,5) for p in ['RearPostPSA','RearPET','RearFoamPSA','RearFoam']]
    expected=base_names+materials+[expected_refs[r] for r in sorted(refs) if r!='J3']
    need(Counter(expected)==Counter(plan['expected_shape_names']) and plan['expected_shape_count']==len(expected),'Independent C1 object names/count')
    need(Counter(materials)==Counter(plan['shape_categories']['materials']),'Material ledger names')
    head=J(V+'freecad_readback.json');gui=J(V+'native_gui_readback.json')
    need(head['status']=='PASS_NATIVE_BREP_READBACK_ONLY' and gui['status']=='PASS_GUI_SAVED_REOPENED_BREP_ONLY' and gui['reopened'] is True,'Native readback status')
    need(head['native_file']==gui['native_file']==Path(NATIVE).name,'Native filename')
    need(head['expected_shape_names']==plan['expected_shape_names'] and head['expected_shape_count']==len(expected) and head['reference_shape_names']==expected_refs,'Headless expectation')
    need(gui['input_before']==gui['input_after']==plan['source_sha256'],'GUI source chain')
    need(gui['headless_native_sha256']==head['native_sha256']==produced[NATIVE],'Headless native chain')
    need(gui['native_sha256']==prov['native_gui_sha256']==sha(path(NATIVE)),'GUI native chain')
    for d in [head,gui]:
        need(set(d['parts'])==set(expected) and len(d['parts'])==len(expected),'Readback object names')
        for n,x in d['parts'].items():need(x['valid'] is True and x['solids']>=1 and x['volume_mm3']>0,'Invalid native shape '+n)
    for n in expected:
        need(abs(head['parts'][n]['volume_mm3']-gui['parts'][n]['volume_mm3'])<1e-5 and head['parts'][n]['solids']==gui['parts'][n]['solids'],'GUI changed geometry '+n)
    with zipfile.ZipFile(path(NATIVE)) as z:
        xml=ET.fromstring(z.read('Document.xml'))
        saved=[x.get('name') for x in xml.findall('./Objects/Object') if x.get('type')=='Part::Feature']
    need(Counter(saved)==Counter(expected),'Saved FCStd object names')
    mechanical=J(V+'mechanical_validation.json')
    need(mechanical['status']=='PASS_ENVELOPE_GEOMETRY_ONLY' and not mechanical['failures'] and all(abs(x)<1e-6 for x in mechanical['interference_mm3'].values()),'Shell geometry')
    export=J(V+'export_validation.json');need(export['status']=='PASS_EXPORT_TOPOLOGY_ONLY','STEP/STL export')
    need(set(export['parts'])=={'front_frame','back_cover'},'Export parts')
    for n,x in export['parts'].items():
        need(x['step_readback']['valid'] and x['step_readback']['solids']==1 and x['step_readback']['volume_mm3']>0 and abs(x['step_volume_delta_mm3'])<1e-5,'STEP validity '+n)
        need(all(x[k]==0 for k in ['stl_unpaired_edges','stl_degenerate_triangles','stl_inconsistent_directed_edges']),'STL topology '+n)
    proxy=J(V+'populated_proxy_validation.json')
    need(proxy['status']=='REVIEW_REQUIRED_RESERVED_SPACE_CONFLICTS' and proxy['component_count']==81 and {x['ref'] for x in proxy['all_per_reference_results']}==refs and len(proxy['all_per_reference_results'])==81,'Proxy coverage')
    need(not proxy['proxy_positive_intersections'] and not proxy['support_courtyard_hits'],'Unreviewed structural interference')
    for row in proxy['all_per_reference_results']:
        need(row['body_geometry']['valid'] and row['body_geometry']['solids']>=1 and all(abs(x)<1e-6 for x in row['intersections_mm3'].values()),'Part geometry/interference '+row['ref'])
    for row in proxy['service_port_checks']:need(abs(row['position_error_mm'])<1e-6 and not row['positive_hits'],'Service port')
    need(proxy['actual_partial_step']['source_sha256']==full and proxy['actual_partial_step']['geometry']['valid'] and all(abs(x)<1e-6 for x in proxy['actual_partial_step']['intersections_mm3'].values()),'Actual partial STEP interference')
    need(all(abs(x)<1e-6 for x in proxy['nominal_source_USB_pose_intersections_mm3'].values()),'USB envelope interference')
    review=J(V+'assembly_review_gates.json')
    need(re.fullmatch('[0-9a-f]{64}',reviewed_sha or '') and sha(path(V+'assembly_review_gates.json'))==reviewed_sha,'Explicit assembly review SHA required')
    need(review['status']=='REVIEW_REQUIRED_ASSEMBLY' and review['manufacturing_release_blocked'] is True and review['geometry_changed_to_hide_conflicts'] is False,'Assembly classification')
    need(review['retained_courtyard_pair_intersections']==proxy['component_pair_positive_intersections'] and review['blocking_reserved_conflicts']==proxy['reserved_space_positive_intersections'],'Original conflict records changed')
    pairs=review['retained_courtyard_pair_intersections'];reserved=review['blocking_reserved_conflicts']
    need(len(pairs)==1 and {pairs[0]['a'],pairs[0]['b']}=={'TP2','TP3'} and pairs[0]['mm3']>0,'Unreviewed courtyard pair')
    need(len(reserved)==5 and {(x['space'],x['ref']) for x in reserved}=={('ph_plug_keepout','SW3')}|{('flex_keepout','C'+str(i)) for i in range(118,122)} and all(x['mm3']>0 for x in reserved),'Unreviewed reserved conflict')
    need(review['test_pad_refinement']['pad_bbox_overlap_mm2']==0 and review['test_pad_refinement']['original_courtyard_shapes_retained'] is True and len(review['required_actions'])>=3,'Test-pad review/required action')
    contact_input=J(V+'pcb_contact_inputs.json');need(contact_input['board_sha256']==board,'Contact input board')
    tps=[]
    for ref in ['TP2','TP3']:
        rows=[x for x in contact_input['pads'] if x['ref']==ref];need(len(rows)==1,'Test-pad geometry');tps.append(rows[0]['bbox'])
    a,b=tps;area=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));need(area==0,'Actual copper test-pad overlap')
    clamp=J(V+'clamping_validation.json')
    need(clamp['status']=='PASS_NOMINAL_C1_GEOMETRY_ONLY' and not clamp['aa_no_press_projection_hits'] and not clamp['positive_intersections'],'Nominal clamp')
    need(Counter(clamp['material_shape_names'])==Counter(materials),'25 material layers')
    need(len(clamp['front_pad_rows'])==3 and all(x['nominal_face_gap_mm']>0 and x['max_local_panel_gap_mm']>0 for x in clamp['front_pad_rows']),'Nominal front gaps')
    need(len(clamp['rear_pad_rows'])==4,'Rear pad count')
    for x in clamp['rear_pad_rows']:
        ratio=1-x['installed_foam_t_mm']/x['free_foam_t_mm']
        need(.2<=ratio<=.3 and abs(ratio-x['compression_ratio'])<1e-9 and abs(x['stack_top_z_mm'])<1e-9,'Rear compression stack')
    need(clamp['measurement_acceptance']=={'front_gap_min_mm':.1,'front_gap_max_mm':.25,'rear_compression_min':.2,'rear_compression_max':.3},'Acceptance range')
    need(clamp['manufacturing_release_blocked'] is True and clamp['open_physical_gates'] and clamp['lateral_capture']['measured_half_play_mm'] is None and clamp['tolerance_stack']['verified_worst_case'] is False,'Physical gates must remain open')
    contact=J(V+'pcb_contact_audit.json')
    need(contact['status']=='PASS_CONSERVATIVE_CONTACT_PROJECTIONS_ONLY' and not contact['exposed_pad_or_via_hits'],'Contact projections')
    need(contact['input_sha256']==sha(path(V+'pcb_contact_inputs.json')) and contact['copper_step_sha256']==sha(path(O+'pcb_copper_audit.step')),'Contact input SHA')
    return {'native_shape_count':len(expected),'native_sha256':gui['native_sha256'],'assembly_review_sha256':reviewed_sha,'blocking_reserved_conflicts':reserved,'manufacturing_release_blocked':True,'production_release':False,'physical_hardware_tested':False}

def procurement():
    report=J('docs/portrait/procurement_candidates.audit.json')
    need(report['status']=='PASS_DOCUMENT_COVERAGE_ONLY' and report['reference_count']==81 and report['fitted_position_count']==78 and report['fab_only_position_count']==3,'Procurement counts')
    need(report['protected_sha256_before']==report['protected_sha256_after'] and report['protected_files_unchanged'] is True,'Procurement source changes')
    same(report['output_sha256'])
    rows=list(csv.DictReader(path('docs/portrait/procurement_candidates.csv').open()))
    refs={x['ref'] for x in J(V+'pcb_model_coverage.json')['parts']}
    need(len(rows)==81 and {x['Reference'] for x in rows}==refs and sum(int(x['PurchaseQtyPerBoard']) for x in rows)==78,'CSV coverage')
    need({x['Reference'] for x in rows if int(x['PurchaseQtyPerBoard'])==0}=={'TP2','TP3','TP4'},'FAB-only test pads')
    need(all(x['PhysicalValidationComplete']=='False' and x['StockVerified']=='False' for x in rows),'Unverified procurement claim')
    for n in ['LICENSES/KiCad-footprints-COPYRIGHT.txt','LICENSES/KiCad-symbols-COPYRIGHT.txt','LICENSES/Espressif-kicad-libraries-LICENSE.md']:
        need(path(n).stat().st_size>500,'Missing library license')

def software_run():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    folder=A+'package-audit-'+stamp+'/'
    (R/folder).mkdir(exist_ok=False)
    log=folder+'software.log';proof=folder+'software-proof.json'
    before=snap(software_inputs());cmd=['bash','tools/portrait_driver/visible_final_checks.sh']
    print('VISIBLE EXECUTION:',cmd,flush=True)
    with (R/log).open('w') as f:
        proc=subprocess.Popen(cmd,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in proc.stdout: print(line,end='',flush=True);f.write(line);f.flush()
        code=proc.wait()
    after=snap(software_inputs())
    record={'command':cmd,'started_utc':stamp,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':code,'input_before':before,'input_after':after,'log':log,'log_sha256':sha(R/log),'physical_hardware_tested':False}
    (R/proof).write_text(json.dumps(record,indent=2)+'\n')
    need(code==0 and before==after,'Software failed or source changed; actual evidence retained in '+folder)
    return proof,[proof,log]

def validate(m):
    need(m['schema']=='p36-source-review-freeze-v3' and m['source_only'] is True and m['manufacturing_release_blocked'] is True,'Freeze type')
    ns=catalog(m['audit_files'])
    need(ns==m['bundle_members'] and set(ns)==set(m['files']),'Bundle whitelist changed')
    for n,x in m['files'].items():need(sha(path(n))==x['sha256'] and path(n).stat().st_size==x['bytes'],'Frozen file changed '+n)
    board,_=electrical();summary=mechanical(board,m['reviewed_assembly_sha256']);procurement()
    proof=J(m['software_proof']);same(proof['input_after'])
    need(proof['exit_code']==0 and proof['input_before']==proof['input_after']==snap(software_inputs()),'Software result/source binding')
    need(proof['log_sha256']==sha(path(proof['log'])),'Software log binding')
    need('SUCCESS' in path(S+'pio.log').read_text() and 'PASS: host software suites and firmware compile' in path(proof['log']).read_text(),'Firmware compile result')
    for name in ['phone-dom.json','phone-core.json']:
        need(J(S+name)['passed'] is True,'Failed software suite '+name)
    phone=J(S+'phone-protocol.json');service=J(S+'phone-service.json')
    need(phone['phone_host_cases']==43 and phone['header_limit']==2048 and phone['body_limit']==4096 and phone['one_frame_bytes']==120000 and phone['no_hardware_or_network'] is True,'Phone protocol report')
    need(service['service_power_model_cases']==23 and service['wake_gpio']==1 and service['wake_mask']==2 and service['usb_adc_gpio']==4 and service['no_real_wifi_or_gpio'] is True,'Service/power model report')
    for x in [J(S+'frame/tests.json')['test_frame'],J(S+'frame/tests.json')['test_transaction']]:need(x['passed'] is True,'Frame tests')
    for name in ['tools/portrait_display/phone/index.html','tools/portrait_display/phone/app.js','firmware/portrait36/include/phone_page.h']:
        text=path(name).read_text()
        need('00000000000000000000000000000000' not in text and not re.search(r'id=["\']token["\'][^>]*value=["\'][^"\']+',text),'Mock credential in production '+name)
    for n,h in m['vendor_sha256'].items():need(sha(vendor/n)==h,'Vendor input changed '+n)
    need(m['vendor_sha256']['EPD_3in6e.cpp']==VENDOR_SHA,'Pinned vendor source')
    need(m['omitted_produced_artifacts']=={EXCLUDED_IMAGE:{'sha256':sha(path(EXCLUDED_IMAGE)),'reason':'Historical render text incorrectly implies implemented door-access credential; root excluded image from ZIP and upload. Source retained for provenance.'}},'Historical image exclusion')
    summary.update(board_sha256=board,erc_errors=0,erc_reviewed_warnings=9,drc_findings=0,net_parity_errors=0,firmware_binary_included=False,source_file_count=len(ns))
    return summary

def freeze():
    need(not M.exists(),'Freeze manifest already exists; do not overwrite')
    need(args.assembly_review_sha256,'Pass explicitly reviewed assembly SHA')
    board,_=electrical();mechanical(board,args.assembly_review_sha256);procurement()
    need((vendor/'EPD_3in6e.cpp').is_file() and (vendor/'EPD_3in6e.h').is_file(),'Vendor oracle files')
    need(sha(vendor/'EPD_3in6e.cpp')==VENDOR_SHA,'Vendor source pin')
    proof,audit=software_run()
    ns=catalog(audit)
    m={'schema':'p36-source-review-freeze-v3','status':'SOURCE_REVIEW_CANDIDATE_WITH_OPEN_ASSEMBLY_BLOCKERS','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_only':True,'manufacturing_release_blocked':True,'physical_hardware_tested':False,'software_proof':proof,'audit_files':audit,'reviewed_assembly_sha256':args.assembly_review_sha256,'bundle_members':ns,'files':{n:{'sha256':sha(path(n)),'bytes':path(n).stat().st_size} for n in ns},'vendor_sha256':{n:sha(vendor/n) for n in ['EPD_3in6e.cpp','EPD_3in6e.h']},'omitted_produced_artifacts':{EXCLUDED_IMAGE:{'sha256':sha(path(EXCLUDED_IMAGE)),'reason':'Historical render text incorrectly implies implemented door-access credential; root excluded image from ZIP and upload. Source retained for provenance.'}},'third_party_license_sources':{'LICENSES/Espressif-kicad-libraries-LICENSE.md':'https://raw.githubusercontent.com/espressif/kicad-libraries/main/LICENSE.md','LICENSES/KiCad-footprints-COPYRIGHT.txt':'/usr/share/doc/kicad-footprints/copyright','LICENSES/KiCad-symbols-COPYRIGHT.txt':'/usr/share/doc/kicad-symbols/copyright'}}
    summary=validate(m);m['summary']=summary
    with M.open('x') as f:json.dump(m,f,indent=2,ensure_ascii=False);f.write('\n')
    print('FROZEN',M,'SHA256',sha(M),json.dumps(summary,ensure_ascii=False),flush=True)

def package():
    need(args.out,'ZIP output path required');out=Path(args.out).resolve()
    need(out.suffix.lower()=='.zip' and not out.exists() and not Path(str(out)+'.sha256').exists(),'Output must be a new ZIP')
    m=json.loads(M.read_text());summary=validate(m)
    files={n:path(n) for n in m['bundle_members']}
    files.update({'third_party/waveshare-3in6e-ESP32/'+n:vendor/n for n in m['vendor_sha256']})
    extras={'FROZEN-INPUTS.json':M.read_bytes(), 'START_HERE.txt':('P36 SOURCE REVIEW CANDIDATE / 源码评审候选\n\n先读 docs/portrait/START_HERE.md\n当前 PH 插头预留与 SW3、FPC 预留与 C118-C121 的五项装配阻断未闭合。禁止生产、下单或强行装配。\nERC 0错误/9条逐项审阅警告；DRC/未连/parity 0。软件host测试和真实编译通过，实体屏/WiFi/ADC/电池/机械/RF未验证。\nNFC/门禁功能尚未设计完成。无可烧录固件；panel-3in6e-native.bin仅是120000B样帧。\nFreeCAD打开 hardware/portrait/enclosure/output/portrait_assembly_revisionB.FCStd；KiCad打开 hardware/portrait/pcb/badge.kicad_pro（含4子sheet）。\n唯一有意省略的最终producer输出为portrait_review_overview.png：旧图文字误导门禁已实现。它仍保留在本地且provenance SHA已核；其冻结源保留供追溯，不代表功能实现。\n已安装工具链与缓存、历史A/旧报告/备份、mock服务器凭据、host可执行文件、router JAR、生产Gerber均不打包。\n详细证据与每个文件SHA见FROZEN-INPUTS.json、PACKAGE-MANIFEST.json和SHA256SUMS.txt。\n').encode('utf-8')}
    evidence={'source_only':True,'firmware_binary_included':False,'not_flashed':True,'physical_hardware_tested':False,'source_sha256':J(m['software_proof'])['input_after'],'software_proof':m['software_proof'],'pio_log_sha256':sha(path(S+'pio.log')),'reason':'Source review delivery; SDK binary redistribution/relink materials not packaged.'}
    extras['firmware/portrait36/BUILD_EVIDENCE.json']=(json.dumps(evidence,indent=2)+'\n').encode()
    info={n:{'sha256':sha(p),'bytes':p.stat().st_size} for n,p in files.items()}
    info.update({n:{'sha256':digest(b),'bytes':len(b)} for n,b in extras.items()})
    package_manifest={'schema':'p36-review-zip-v3','summary':summary,'files':info,'omitted_produced_artifacts':m['omitted_produced_artifacts'],'no_manufacturing_release':True}
    extras['PACKAGE-MANIFEST.json']=(json.dumps(package_manifest,indent=2,ensure_ascii=False)+'\n').encode()
    hashes={n:x['sha256'] for n,x in info.items()};hashes['PACKAGE-MANIFEST.json']=digest(extras['PACKAGE-MANIFEST.json'])
    extras['SHA256SUMS.txt']=''.join(h+'  '+n+'\n' for n,h in sorted(hashes.items())).encode()
    hashes['SHA256SUMS.txt']=digest(extras['SHA256SUMS.txt'])
    prefix='P36-review-candidate/'
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
        for n in sorted(set(files)|set(extras)):
            need(n!=EXCLUDED_IMAGE and allowed(n),'Excluded or unsafe member '+n)
            data=files[n].read_bytes() if n in files else extras[n]
            need(digest(data)==hashes[n],'Changed during ZIP '+n)
            zi=zipfile.ZipInfo(prefix+n,date_time=(1980,1,1,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=0o100644<<16
            z.writestr(zi,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(out) as z:
        need(z.testzip() is None,'ZIP CRC check')
        need(set(z.namelist())=={prefix+n for n in hashes} and len(z.namelist())==len(hashes),'ZIP member list')
        for n,h in hashes.items():need(digest(z.read(prefix+n))==h,'ZIP readback SHA '+n)
    validate(m)
    with Path(str(out)+'.sha256').open('x') as f:f.write(sha(out)+'  '+out.name+'\n')
    print('ZIP VERIFIED',out,'BYTES',out.stat().st_size,'SHA256',sha(out),'MEMBERS',len(hashes),flush=True)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode',choices=['freeze','zip'])
parser.add_argument('--repo',required=True);parser.add_argument('--vendor',required=True)
parser.add_argument('--manifest',default=A+'package-freeze.json')
parser.add_argument('--assembly-review-sha256');parser.add_argument('--out')
args=parser.parse_args();R=Path(args.repo).resolve();vendor=Path(args.vendor).resolve();M=R/args.manifest
need(M.resolve().is_relative_to(R) and M.parent.is_dir(),'Unsafe manifest location')
if args.mode=='freeze':freeze()
else:package()
