"""C1 geometry extension; all calculations in the mechanical finished-board frame.
Raw KiCad STEP remains untouched. The explicit +0.045 Z map follows the GUI stackup.
"""
import json
import cadquery as cq
import c1_config as K
from cad_helpers import front_box, inspect, export_part, render_shapes

def install(M):
    old_frame,old_cover,old_refs,old_validate=M.frame,M.cover,M.reference_bodies,M.validate
    T=M.C['retention']
    def shoulder_shapes():
        return {n:M.rr_front(r,*T['shoulder_z'],.3) for n,r in T['shoulders'].items()}
    def guide_shapes():
        return {n:M.rr_front(r,*T['guide_z'],.15) for n,r in T['guides'].items()}
    def frame():
        s=old_frame()
        for p in list(shoulder_shapes().values())+list(guide_shapes().values()): s=s.fuse(p)
        for r in T['strips'].values():
            x0,y0,x1,y1=r
            s=s.cut(front_box((x0-.10,y0-.10,x1+.10,y1+.10),M.BEZEL_BOTTOM-.01,T['front_seat_z']))
        return s.clean()
    def cover():
        s=old_cover()
        for r in M.SUPPORTS: s=s.cut(front_box(r,T['rear_post_top_z'],.01))
        return s.clean()
    def reference_bodies():
        r=old_refs(); p=M.P; z=M.PANEL_BOTTOM; y=T['panel_bottom_band_y']
        r['panel_global_audit']=r['panel']
        upper=front_box((p['x'],p['y'],p['x']+p['w'],y),z,z+T['panel_upper_max_t'])
        lower=front_box((p['x'],y,p['x']+p['w'],p['y']+p['h']),z,z+p['t_max'])
        r['panel']=upper.fuse(lower).clean()
        r['aa_no_press_audit']=front_box(T['aa_no_press_rect'],M.BT,M.BEZEL_BOTTOM)
        r['battery_envelope']=front_box(M.C['battery']['rect'],-M.C['battery']['max_envelope_t']-.1,-.1)
        r['usb_outline']=r['usb_outline'].translate((0,0,T['raw_to_mechanical_z']))
        r['pcb_actual_core']=cq.importers.importStep(str(M.OUT/'pcb_board_body.step')).val().translate((0,0,T['raw_to_mechanical_z']))
        for side,rect in T['strips'].items():
            r['ScreenPSA_'+side]=front_box(rect,M.BT,M.PANEL_BOTTOM)
            seat=T['front_seat_z']; glue=T['front_psa_t']; foam=T['front_foam_t']
            r['FrontPSA_'+side]=front_box(rect,seat-glue,seat)
            r['FrontFoam_'+side]=front_box(rect,seat-glue-foam,seat-glue)
        for i,rect in enumerate(M.SUPPORTS,1):
            z=T['rear_post_top_z']
            for prefix,t in [('RearPostPSA',T['rear_post_psa_t']),('RearPET',T['rear_pet_t']),('RearFoamPSA',T['rear_foam_psa_t']),('RearFoam',T['rear_foam_installed_t'])]:
                r[prefix+'_'+str(i)]=front_box(rect,z,z+t); z+=t
            assert abs(z)<1e-8
        return r
    def validate(parts,refs):
        result=old_validate(parts,refs)
        result.update(K.fingerprints(M.C))
        result['source_config']='c1_config.configure(read-only hardware/pcb/scripts/design.py::PORTRAIT)'
        result['clearance_budget_mm']['battery_envelope_to_cover']=.5
        result['clearance_budget_mm']['front_soft_stop_to_nominal_screen']=T['front_seat_z']-T['front_psa_t']-T['front_foam_t']-(M.PANEL_BOTTOM+M.P['t'])
        result['limitations']=K.OPEN_GATES
        result['raw_to_mechanical_transform']={'translation_mm':[0,0,T['raw_to_mechanical_z']],'rotation_deg':[0,0,0],'scale':[1,1,1],'source':'validation/stackup_gui_observed.txt: bottom copper0.035 + bottom mask0.010; raw STEP retained'}
        result['rear_support_contact']='Solid post stops at Z-0.85; two adhesive layers/PET/compressed foam end at Z0; no direct post-to-PCB contact.'
        (M.REPORT/'mechanical_validation.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    def main():
        pins=json.loads((M.REPORT/'eda_frozen_inputs.json').read_text())
        assert all(K.digest(M.ROOT/p)==h for p,h in pins.items()), 'Frozen electrical input changed'
        coverage=json.loads((M.REPORT/'pcb_model_coverage.json').read_text())
        plan=K.expectation(coverage,M.C)
        (M.REPORT/'mechanical_expectation.json').write_text(json.dumps(plan,indent=2)+'\n')
        parts={'front_frame':frame(),'back_cover':cover()}; refs=reference_bodies()
        result=validate(parts,refs)
        for key,shape in parts.items(): export_part(shape,M.OUT/('portrait_'+key))
        geometry={**refs,**parts}; reference_checks={}
        assembly=cq.Assembly(name='P36_REVISION_B_C1_NOMINAL')
        for name,key,category in K.OBJECTS:
            shape=geometry[key]; q=inspect(shape)
            assert q['valid'] and q['solids']==1,(name,q)
            reference_checks[name]=q
            if category!='structure': cq.exporters.export(shape,str(M.OUT/('reference_'+key+'.step')))
            if category not in ('audit','space_reserve'):
                color=(.3,.36,.42) if category=='structure' else (.87,.77,.45) if category=='materials' else (.2,.45,.33) if key=='pcb_actual_core' else (.82,.83,.80)
                assembly.add(shape,name=name,color=cq.Color(*color))
        assembly.save(str(M.OUT/'portrait_assembly.step'))
        (M.REPORT/'c1_reference_geometry.json').write_text(json.dumps({**K.fingerprints(M.C),'status':'PASS_REFERENCE_SOLIDS_ONLY','parts':reference_checks},indent=2)+'\n')
        (M.OUT/'mechanical_dimensions.json').write_text(json.dumps({'canonical':M.C,'derived':result},indent=2)+'\n')
        render_shapes([(parts['front_frame'],'#344554'),(refs['panel'],'#ece8dc')],M.OUT/'portrait_iso_front.png','C1 nominal CAD | 66 x 109 x 11.1 mm | no physical-fit approval')
        exploded=[(parts['front_frame'].translate((0,0,12)),'#344554'),(refs['panel'].translate((0,0,6)),'#ece8dc'),(refs['pcb_actual_core'],'#367957'),(refs['battery_envelope'],'#aab3bb'),(parts['back_cover'].translate((0,0,-12)),'#647b8c')]
        render_shapes(exploded,M.OUT/'portrait_exploded.png','C1 separated stack | actual board core + explicitly named envelopes',elevation=32,azimuth=-62)
        assert all(K.digest(M.ROOT/p)==h for p,h in pins.items())
        print(json.dumps({'status':result['status'],'revision':K.DESIGN_REVISION,'native_expected_shapes':plan['expected_shape_count'],'reference_solids_checked':len(reference_checks),'dimensions_mm':[M.E['outer_w'],M.E['outer_h'],M.FRONT-M.BACK]},indent=2))
    M.frame=frame; M.cover=cover; M.reference_bodies=reference_bodies
    M.shoulder_shapes=shoulder_shapes; M.guide_shapes=guide_shapes
    M.validate=validate; M.main=main
