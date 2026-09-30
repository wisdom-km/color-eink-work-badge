"""Nominal USB approach gauge and reserved battery-plug/lead bay checks.
Nothing here claims102mm real cable can be packed or that any USB cable fits.
"""
import json
import build_enclosure as M
from cad_helpers import front_box,overlap_volume
case={'front_frame':M.frame(),'back_cover':M.cover()};ref=M.reference_bodies()
a=M.C['usb']['approach'];r=a['rect'];gauge=front_box((r[0],r[1],r[2],r[3]+20),a['z_min'],a['z_max'])
# This single sweptprism covers insertion from outside to y93 at every point.
usb={name:overlap_volume(gauge,s) for name,s in case.items()}
reserved={name:{c:overlap_volume(ref[name],s) for c,s in case.items()} for name in ('wire_keepout','ph_plug_keepout')}
internal={'battery_to_ph_plug_gap_mm':ref['battery_envelope'].distance(ref['ph_plug_keepout']),
          'battery_vs_ph_plug_overlap_mm3':overlap_volume(ref['battery_envelope'],ref['ph_plug_keepout']),
          'battery_vs_wire_bay_overlap_mm3':overlap_volume(ref['battery_envelope'],ref['wire_keepout'])}
assert all(v<1e-6 for v in usb.values())
assert all(v<1e-6 for x in reserved.values() for v in x.values())
report={'status':'PASS_NOMINAL_RESERVED_ACCESS_NOT_REAL_CABLE_FIT',
        'usb_gauge_mm':a['gauge_mm'],'usb_swept_intersections_mm3':usb,
        'usb_nominal_gauge_wall_clearance_mm':0,
        'usb_front_roof_min_mm':M.FRONT-a['z_max'],
        'usb_rear_wall_min_mm':a['z_min']-M.BACK,
        'battery_and_connector_reserved_checks':reserved,'internal':internal,
        'requirements':['15x6.5 is the allocatedclearance envelope. A physicalovermold must be smaller, with manufacturing and alignment margin.',
        'No universalUSBcable compatibility. The gauge only proves there is no solids blocking the nominal approach path.',
        'OriginalAdafruit leadlength100-102mm and PH plug require physical loosebend/strainrelief checks. A clear bayvolume is not a routed wire.',
        '0.5mm battery-to-PH reservedgap does not prove the leadexit bend fits.']} 
(M.REPORT/'access_space_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
