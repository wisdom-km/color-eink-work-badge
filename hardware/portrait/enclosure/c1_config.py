"""C1 mechanical-only overlay. Frozen electrical sources are read-only.
Nominal retention candidate, not a manufacturing or panel-pressure approval.
"""
from pathlib import Path
from copy import deepcopy
import hashlib, json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DESIGN_REVISION='P1.1-revisionB-C1'
BOARD_SHA='a6e52a432d860a8ce0d489fdaac9a9f9a56ae2c96e7ca05ce998e5b3b5a1cd40'
PANEL_SOURCE='https://files.waveshare.com/wiki/3.6inch_e-Paper_HAT%2B_E/3.6inch_e-Paper_HAT%2B.pdf'
SOURCES={
 'screen_drawing':PANEL_SOURCE,
 'screen_tape':'https://multimedia.3m.com/mws/media/2522783O/3m-adhesive-transfer-tape-468mp.pdf',
 'rear_foam':'https://www.rogerscorp.com/-/media/project/rogerscorp/documents/elastomeric-material-solutions/poron/english/data-sheets/17-006-poron-4701-30-very-soft.pdf',
 'front_foam':'https://www.rogerscorp.com/-/media/project/rogerscorp/documents/elastomeric-material-solutions/poron/english/data-sheets/17-469-poron-4790-92pl-09-extra-soft-slow-rebound-data-sheet.pdf',
 'step_datum':'https://gitlab.com/kicad/code/kicad/-/raw/10.0.6/pcbnew/exporters/step/step_pcb_model.cpp'}
STRIPS={'Left':[1.65,4,2.55,74],'Right':[55.45,4,56.35,74],'Top':[4,.65,54,1.55]}
SHOULDERS={
 'L1':[-.7,2.2,.45,4.2],'L2':[-.7,44,.45,48],'L3':[-.7,70,.45,74],
 'R1':[57.55,18,58.7,20],'R2':[57.55,44,58.7,48],'R3':[57.55,70,58.7,74]}
GUIDES={'L1':[-.7,10,-.10,14],'L2':[-.7,68,-.10,72],'R1':[58.10,40,58.7,44]}
OPEN_GATES=[
 'Manufacturing blocked until measured front gaps are positive and within0.10..0.25mm; nominal clearances are not a worst-case guarantee.',
 'Measure local PCB bearing thickness and post/shoulder separation; select rear PET shims for20..30 percent foam compression.',
 'Measure PCB lateral play and panel placement; nominal58.20 guide width is not a measured tolerance guarantee.',
 'Screen glass/PS/FPL edge-pressure and adhesive compatibility are not approved by the panel manufacturer.',
 'Inspect PCB flatness after reflow before bonding glass; never use case screws to force a warped PCB or glass flat.',
 'UPDATE rest clearance does not prove operation: measure gap0.10..0.20, actual stroke/stop and safe overtravel; no preload or stuck wake.',
 'FPC fold length/bend radius, original100..102mm leads/PH mating, exact USB cable, thermal, RF, impact and fatigue require first article.',
 'No universal door-access compatibility or manufacturing-release claim.']

def configure(base):
    c=deepcopy(base); c['version']=DESIGN_REVISION
    c['enclosure']['panel_adhesive']=.13
    c['enclosure']['panel_gasket']=.17
    c['retention']={
      'strips':STRIPS,'shoulders':SHOULDERS,'guides':GUIDES,
      'shoulder_z':[.8,1.8],'guide_z':[-.6,.7],
      'rear_post_top_z':-.85,'rear_post_psa_t':.05,'rear_pet_t':.15,
      'rear_foam_psa_t':.05,'rear_foam_free_t':.79,'rear_foam_installed_t':.60,
      'front_seat_z':2.45,'front_foam_t':.50,'front_psa_t':.06,
      'front_foam_thickness_tolerance_mm':.10,'illustrative_seat_low_error_mm':.05,
      'front_seat_allowed_z':[2.30,2.60],'minimum_front_roof_mm':.90,
      'front_gap_acceptance_mm':[.10,.25],'rear_compression_acceptance':[.20,.30],
      'aa_no_press_rect':[3.1,2.1,54.9,79.3],
      'panel_upper_max_t':.85,'panel_bottom_band_y':77.6,
      'raw_to_mechanical_z':.045,
      'stackup_nominal_mm':{'F.Mask':.010,'F.Cu':.035,'core':.710,'B.Cu':.035,'B.Mask':.010},
      'sources':SOURCES,'manufacturing_release_blocked':True,'open_gates':OPEN_GATES}
    return c

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fingerprints(c):
    return {'design_revision':DESIGN_REVISION,
      'base_design_sha256':digest(ROOT/'hardware/pcb/scripts/design.py'),
      'c1_config_sha256':digest(__file__),
      'config_sha256':hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),
      'board_sha256':digest(ROOT/'hardware/portrait/pcb/badge.kicad_pcb')}

# Predeclared native Object.Name -> reference body key -> category.
OBJECTS=[
 ('FrontFrame','front_frame','structure'),('BackCover','back_cover','structure'),
 ('Display_Local_Max_Envelope','panel','electronic_reference'),
 ('PCB_0p8_Envelope','pcb_placeholder','audit'),
 ('PCB_KiCad_Core_In_Mechanical_Frame','pcb_actual_core','electronic_reference'),
 ('Battery_Adafruit1578_Envelope','battery_envelope','electronic_reference'),
 ('USB_HRO_Body_Envelope','usb_outline','electronic_reference'),
 ('Lead_Clearance_Reserve','wire_keepout','space_reserve'),
 ('PH_Plug_Clearance_Reserve','ph_plug_keepout','space_reserve'),
 ('Display_Global_1p2_Audit','panel_global_audit','audit'),
 ('AA_NoPress_Audit','aa_no_press_audit','audit')]
for side in STRIPS:
    for prefix in ('ScreenPSA','FrontFoam','FrontPSA'):
        name=prefix+'_'+side; OBJECTS.append((name,name,'materials'))
for i in range(1,5):
    for prefix in ('RearPostPSA','RearPET','RearFoamPSA','RearFoam'):
        name=prefix+'_'+str(i); OBJECTS.append((name,name,'materials'))
assert len(OBJECTS)==36 and sum(cat=='materials' for _,_,cat in OBJECTS)==25

def expectation(coverage,c):
    assert coverage['footprint_count']==81 and coverage['board_sha256']==BOARD_SHA
    names=[n for n,_,_ in OBJECTS]
    mapping={p['ref']:('USB_HRO_Body_Envelope' if p['ref']=='J3' else 'Envelope_'+p['ref']) for p in coverage['parts']}
    proxies=sorted(n for r,n in mapping.items() if r!='J3')
    categories={k:[n for n,_,cat in OBJECTS if cat==k] for k in sorted(set(cat for _,_,cat in OBJECTS))}
    categories['component_proxy']=proxies
    names+=proxies
    assert len(names)==len(set(names))==116 and len(mapping)==81
    result=fingerprints(c)
    result.update(expected_shape_names=names,expected_shape_count=len(names),shape_categories=categories,reference_shape_names=mapping,minimum_reference_count=81,approved_by='root',approval_scope='Candidate modeling only; no manufacturer or production approval')
    result['source_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sorted(list(HERE.glob('*.py'))+list(HERE.glob('*.FCMacro')))}
    return result
