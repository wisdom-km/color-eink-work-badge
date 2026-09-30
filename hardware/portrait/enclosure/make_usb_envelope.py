"""Build P36-only HRO nominal body envelope from the manufacturer drawing.
Not detailed vendor CAD, not welding lug/plug geometry, no H2 writes.
"""
from pathlib import Path
import sys,json,hashlib
import cadquery as cq
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'hardware/pcb/scripts'));import design
u=design.PORTRAIT['usb'];w,l,t=u['body_size']
shape=cq.Solid.makeBox(w,l,t,cq.Vector(-w/2,-l/2,u['body_f_z_min']))
target=ROOT/'hardware/portrait/pcb/lib/3d/TYPE-C-31-M-14.step'
cq.exporters.export(shape,str(target))
report={'source':'HRO TYPE-C-31-M-14 manufacturer drawing dated2017-12-26, page1',
 'source_dimensions_mm':{'body':[w,l,t],'weld_lug_total_width':11.15,'specified_pcb_thickness':.75},
 'model_frame':'Front-mount STEP, origin XY body center; Z[-.85,+2.01] from drawing mountingdatum',
 'required_footprint_offset':u['model_offset'],
 'derived_B_mount_mm':{'center_front_xy':[50,89.19],'nominal_body_rect':[45.53,85.21,54.47,93.17],'mounting_datum_z':[-2.01,.85]},
 'exporter_note':'KiCad9 currently shifts B-side models-0.085mm vs dielectricback0; inspect actual exported bounds rather than baking an unexplained correction',
 'uncertainties':['Two independent nose positions93.13/93.17 differ0.04mm','Drawing0.75board versus candidate0.8 needsphysical sample','Nominalbody only: source general dimension tolerances, welded lugs, shellvoids and overmold not represented','Solid envelope may overlap intended PCB mating area; this is not detailed contact CAD'],
 'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'scope':'P36 only; H2 model unchanged'}
(HERE/'validation/usb_envelope_source.json').write_text(json.dumps(report,indent=2)+'\n')
print(target)
