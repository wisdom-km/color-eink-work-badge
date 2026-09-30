"""BADGE P1: editable portrait mechanical concept, NOT fabrication release.

Run: python hardware/portrait/enclosure/build_enclosure.py
Canonical product dimensions: hardware/pcb/scripts/design.py::PORTRAIT.
No change to H2 PCB/enclosure. All electronic bodies below are envelopes.
Frame uses X right / Y up / Z towards wearer-visible display. Front-view input
rectangles remain X right / Y down. PCB back = Z0, front = +board.t.
"""
from pathlib import Path
import sys, json, math, hashlib
import cadquery as cq
from cad_helpers import box, front_box, rounded_box, cylinder, inspect, export_part, overlap_volume, render_shapes

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "hardware/pcb/scripts"))
import design
from c1_config import configure
C = configure(design.PORTRAIT)
B, P, E, CARD = (C[k] for k in ("board", "panel", "enclosure", "card"))
OUT = HERE / "output"
REPORT = HERE / "validation"
OUT.mkdir(exist_ok=True); REPORT.mkdir(exist_ok=True)

BW, BH, BT = B["w"], B["h"], B["t"]
OX0 = -(E["outer_w"] - BW) / 2
OX1 = OX0 + E["outer_w"]
TOP = -E["top_extension"]
BOTTOM = TOP + E["outer_h"]
PANEL_BOTTOM = BT + E["panel_adhesive"]
PANEL_TOP = PANEL_BOTTOM + P["t_max"]
BEZEL_BOTTOM = PANEL_TOP + E["panel_gasket"]
FRONT = BEZEL_BOTTOM + E["bezel_t"]
COVER_IN = -E["back_space"]
BACK = COVER_IN - E["back_cover_t"]
CARD_FLOOR = BACK - CARD["slot_t"]
CARD_BACK = CARD_FLOOR - CARD["wall_t"]
CORNER_R = 5.0
CARD_ENABLED = bool(CARD.get("enabled", False))

# Derived structural details. Future PCB must honor these explicitly reserved
# support-contact zones. They are NOT verified against a finished PCB.
SUPPORTS = E['pcb_support_rects']

# Top screws outside the insertion sweep of a full-width access card.
SCREWS = [(OX0+3.7, TOP+4.5), (OX1-3.7, TOP+4.5),
          (6.0, BOTTOM-3.5), (E.get("bottom_right_screw_x", BW), BOTTOM-3.5)]
NUT_AF, NUT_T, NUT_SLOT_W, NUT_SLOT_T = 4.0, 1.6, 4.2, 1.8
NUT_Z = -0.2
LANYARD_RECT = (BW/2-9, TOP+2.8, BW/2+9, TOP+6.2)


def rr_front(rect, z0, z1, radius):
    x0,y0,x1,y1 = rect
    return rounded_box(x0,-y1,z0,x1,-y0,z1,radius)


def slot_lanyard(z0, z1):
    return rr_front(LANYARD_RECT, z0, z1, 1.65)


def screw_cut(shape, z0, z1, countersink_at=None):
    for x,y in SCREWS:
        shape = shape.cut(cylinder(x,-y,z0,z1,2.25))
        if countersink_at is not None:
            # 90 degree countersink: max dia4.05, depth0.9, throat2.25.
            cone = cq.Solid.makeCone(2.025,1.125,0.9,cq.Vector(x,-y,countersink_at),cq.Vector(0,0,1))
            shape = shape.cut(cone)
    return shape


def frame():
    shell = rr_front((OX0,TOP,OX1,BOTTOM), COVER_IN, FRONT, CORNER_R)
    gap = E["edge_clearance"]
    shell = shell.cut(front_box((-gap,-gap,BW+gap,BH+gap),COVER_IN-1,BEZEL_BOTTOM))
    shell = shell.cut(front_box(P["window_rect"],BEZEL_BOTTOM-0.01,FRONT+1))
    shell = shell.cut(slot_lanyard(COVER_IN-1,FRONT+1))
    # Reserved USB access tunnel, not a claim of a verified connector fit.
    u=C["usb"]; half=u["opening_width"]/2
    shell = shell.cut(front_box((u["center"]-half,BH-1,u["center"]+half,BOTTOM+1),u["z_min"],u["z_max"]))
    if u.get('approach'):
        a=u['approach'];shell=shell.cut(front_box(a['rect'],a['z_min'],a['z_max']))
    shell = screw_cut(shell,COVER_IN-1,E.get("screw_blind_top_z",NUT_Z+NUT_T+0.3))
    # Slide-in M2 nut channels from top and bottom outer edges. These are open
    # channels; when screws are removed retain loose nuts with removable tape.
    for i,(x,y) in enumerate(SCREWS):
        ymin,ymax=(TOP-1,y+2.45) if i<2 else (y-2.45,BOTTOM+1)
        shell=shell.cut(front_box((x-NUT_SLOT_W/2,ymin,x+NUT_SLOT_W/2,ymax),
                                 NUT_Z-0.1,NUT_Z-0.1+NUT_SLOT_T))
    if E.get('update_button'):
        b=E['update_button'];x,y=b['x'],b['y']
        shell=shell.cut(front_box((x-3.55,y-1.25,x-2.35,y+1.25),COVER_IN-.05,BACK+b['beam_t']+b['hard_stop_travel']+.95))
    return shell.clean()


def update_stem():
    b=E['update_button'];x,y=b['x'],b['y'];z=BACK+b['beam_t']
    base=cylinder(x,-y,z-.02,-4.0,2.2)
    neck=cq.Workplane('XY').newObject([cylinder(x,-y,-4.02,b['tip_z'],1.2)]).edges('>Z').fillet(.2).val()
    return base.fuse(neck).clean()


def update_stop():
    b=E['update_button'];x,y=b['x'],b['y'];z=BACK+b['beam_t']+b['hard_stop_travel']
    return front_box((x-3.3,y-1,x-1.4,y+1),z,z+.8).fuse(front_box((x-3.3,y-1,x-2.5,y+1),COVER_IN-.05,z+.8)).clean()


def cover():
    shape = rr_front((OX0,TOP,OX1,BOTTOM),BACK,COVER_IN,CORNER_R)
    shape = shape.cut(slot_lanyard(BACK-1,COVER_IN+1))
    for r in SUPPORTS:
        shape=shape.fuse(front_box(r,COVER_IN-0.02,0))
        # Broaden the lower post base after increasing depth; stays below electronics.
        if E['back_space']>4:
            x0,y0,x1,y1=r
            base=(max(-.2,x0-1),max(-.2,y0-1),min(BW+.2,x1+1),min(BH+.2,y1+1))
            shape=shape.fuse(front_box(base,COVER_IN-0.02,-3.2))
    if C['usb'].get('approach'):
        a=C['usb']['approach'];shape=shape.cut(front_box(a['rect'],a['z_min'],a['z_max']))
    shape = screw_cut(shape,BACK-1,0.1,countersink_at=BACK)
    # Recessed service holes align to the current75-part PCB source.
    for button in E.get('service_buttons', []):
        x,y=button['x'],button['y']
        shape=shape.cut(cylinder(x,-y,BACK-1,COVER_IN+0.01,button['hole_d']))
        shape=shape.cut(cylinder(x,-y,BACK-0.01,BACK+0.25,button['hole_d']+1.2))
    if E.get('update_button'):
        b=E['update_button'];x,y=b['x'],b['y'];w=b['beam_w'];end=y+b['beam_length'];start=y-2;slot=b['isolation_slot']
        # Thin the cantilever from the INSIDE: exterior remains flush/one piece.
        shape=shape.cut(front_box((x-w/2,start,x+w/2,end),BACK+b['beam_t'],COVER_IN+.1))
        shape=shape.cut(front_box((x-w/2-slot,start-slot,x-w/2,end),BACK-.1,COVER_IN+.1))
        shape=shape.cut(front_box((x+w/2,start-slot,x+w/2+slot,end),BACK-.1,COVER_IN+.1))
        shape=shape.cut(front_box((x-w/2-slot,start-slot,x+w/2+slot,start),BACK-.1,COVER_IN+.1))
        shape=shape.fuse(update_stem()).fuse(update_stop())
    return shape.clean()


def card_bounds():
    x0=(BW-CARD["w"])/2
    return x0,CARD["top_y"],x0+CARD["w"],CARD["top_y"]+CARD["h"]


def sleeve():
    """Separate removable rear card carrier; top open, retention via label tab."""
    x0,y0,x1,y1=card_bounds(); clr=CARD["xy_clearance"]
    pocket=(x0-clr,y0-1,x1+clr,y1+clr)
    outside=(x0-clr-2,y0,x1+clr+2,y1+clr+2)
    body=rr_front(outside,CARD_BACK,BACK,1.0)
    # A floor and two side rails with bottom stop, no top rail.
    body=body.cut(front_box(pocket,CARD_FLOOR,BACK+1))
    # Finger recess at top of floor to extract a flush card.
    body=body.cut(cylinder(BW/2,-(y0+1.5),CARD_BACK-1,CARD_FLOOR+0.01,18))
    # Mounting ears run beside the card sweep. Top ends cannot obstruct card.
    for i,(x,y) in enumerate(SCREWS):
        if i<2:
            left=x<BW/2
            ex0,ex1=(OX0+0.4,x0-clr) if left else (x1+clr,OX1-0.4)
            ear=front_box((ex0,TOP+0.4,ex1,y0+3),CARD_BACK,BACK)
        else:
            ear=front_box((x-2.6,y1+0.5,x+2.6,BOTTOM-0.4),CARD_BACK,BACK)
        body=body.fuse(ear)
    body=screw_cut(body,CARD_BACK-1,BACK+1,countersink_at=CARD_BACK)
    return body.clean()


def reference_bodies():
    panel=front_box((P['x'],P['y'],P['x']+P['w'],P['y']+P['h']),PANEL_BOTTOM,PANEL_TOP)
    # Deliberately plain FR4 envelope: no trace, net, FPC connector, or route.
    pcb=rr_front((0,0,BW,BH),0,BT,2.0)
    if B.get('fpc_slot'): pcb=pcb.cut(front_box(B['fpc_slot'],-1,BT+1))
    u=C['usb']; pcb=pcb.cut(front_box((u['center']-4.675,BH-6.05,u['center']+4.675,BH+1),-1,BT+1))
    battery=front_box(C['battery']['rect'],-C['battery']['max_envelope_t'],-0.1)
    x0,y0,x1,y1=card_bounds()
    card=rr_front((x0,y0,x1,y1),CARD_FLOOR+0.2,CARD_FLOOR+0.2+CARD['t'],2.8)
    f=C['fpc_keepout']; flex=front_box(f['rect'],f['z_min'],f['z_max'])
    # Whole-board component budget, with support contact zones subtracted.
    component_space=front_box((0,0,BW,BH),-2.4,0)
    for r in SUPPORTS:
        component_space=component_space.cut(front_box(r,-3,0.1))
    u=C['usb'];bw,bl,bt=u['body_size'];cy=BH-2.7-u['model_offset'][1]
    usb=front_box((u['center']-bw/2,cy-bl/2,u['center']+bw/2,cy+bl/2),-u['body_f_z_max']-.085,-u['body_f_z_min']-.085)
    w=C['wire_keepout'];wire=front_box(w['rect'],w['z_min'],w['z_max'])
    pp=C['battery_plug_keepout'];plug=front_box(pp['rect'],pp['z_min'],pp['z_max'])
    return dict(panel=panel,pcb_placeholder=pcb,battery_envelope=battery,
                issued_card_reference=card,flex_keepout=flex,component_budget=component_space,
                usb_outline=usb,wire_keepout=wire,ph_plug_keepout=plug)


def nut(x,y):
    # Across flats =4mm; rotate hex 30deg to obtain flat sides along X.
    r=NUT_AF/math.sqrt(3)
    pts=[(x+r*math.cos(math.radians(30+i*60)),-y+r*math.sin(math.radians(30+i*60))) for i in range(6)]
    shape=cq.Workplane('XY').polyline(pts).close().extrude(NUT_T).val().translate((0,0,NUT_Z))
    return shape.cut(cylinder(x,-y,NUT_Z-1,NUT_Z+NUT_T+1,2.0))


def validate(parts, refs):
    checks={}
    for name,sh in parts.items():
        data=inspect(sh)
        assert data['valid'] and data['solids']==1, (name,data)
        checks[name]=data
    interference={}
    from itertools import combinations
    pairs=list(combinations(parts,2))
    for a,b in pairs:
        interference[f'{a} vs {b}']=overlap_volume(parts[a],parts[b])
    for p in parts:
        for r in ('panel','pcb_placeholder','battery_envelope','flex_keepout','component_budget','usb_outline','wire_keepout','ph_plug_keepout') + (('issued_card_reference',) if CARD_ENABLED else ()):
            interference[f'{p} vs {r}']=overlap_volume(parts[p],refs[r])
    for i,n in enumerate([nut(x,y) for x,y in SCREWS]):
        interference[f'front_frame vs nut_{i}']=overlap_volume(parts['front_frame'],n)
    failures={k:v for k,v in interference.items() if v>1e-5}
    # Known derivative dimensions, not thermal/shock/RF/print tolerance proof.
    result={
      'status':'PASS_ENVELOPE_GEOMETRY_ONLY' if not failures else 'FAIL',
      'source_config':'hardware/pcb/scripts/design.py::PORTRAIT',
      'config_sha256':hashlib.sha256(json.dumps(C,sort_keys=True).encode()).hexdigest(),
      'cadquery':cq.__version__,'parts':checks,'interference_mm3':interference,'failures':failures,
      'dimensions_mm':{'main':[E['outer_w'],E['outer_h'],FRONT-BACK],
                        'external_card_carrier_enabled':CARD_ENABLED},
      'clearance_budget_mm':{'pcb_edge':E['edge_clearance'],'legacy_2p4_height_reference_to_cover':E['back_space']-2.4,
                            'battery_envelope_to_cover':E['back_space']-C['battery']['max_envelope_t'],
                            'panel_nominal_surface_to_bezel':BEZEL_BOTTOM-(PANEL_BOTTOM+P['t']),
                            'nut_slot_width_total':NUT_SLOT_W-NUT_AF,'nut_slot_height_total':NUT_SLOT_T-NUT_T},
      'pcb_support_contact_rectangles_front_view_mm':SUPPORTS,
      'screw_centers_front_view_mm':SCREWS,
      'limitations':['No completed portrait PCB: electronic geometry is only an envelope',
        'Conservative full-panel 1.2mm envelope includes local fanout/UV glue; FPC fold and actual module tolerances remain unverified',
        'USB connector body, plug overmold, FPC bend radius/length, PCM, wires and cell swelling need physical proof',
        'No internal access credential is selected or modeled; no door-access compatibility claim',
        'Panel uses conservative1.2mm envelope; actual gasket/shim thickness and axial clamping are unresolved',
        'M2 nut channel, countersink and10mm screw length need a printed fit coupon',
        'Access-card RF interoperability/read distance is untested with PCB, battery and second NFC antenna',
        'No physical print, ingress, impact, pull-load, thermal, battery safety or live-device tests'],
    }
    (REPORT/'mechanical_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    assert not failures, failures
    return result


def main():
    parts={'front_frame':frame(),'back_cover':cover()}
    if CARD_ENABLED: parts['card_sleeve']=sleeve()
    refs=reference_bodies()
    result=validate(parts,refs)
    for name,shape in parts.items():
        export_part(shape,OUT/f'portrait_{name}')
    # STEP assembly is a set of separate colored objects, not a fused body.
    assembly=cq.Assembly(name='BADGE_P1_CONCEPT')
    colors={'front_frame':(0.10,0.14,0.19),'back_cover':(0.21,0.26,0.31),'card_sleeve':(0.14,0.18,0.22)}
    for name,shape in parts.items(): assembly.add(shape,name=name,color=cq.Color(*colors[name]))
    for name,col in [('panel',(0.94,0.93,0.89)),('pcb_placeholder',(0.12,0.45,0.30)),('battery_envelope',(0.7,0.72,0.74)),('usb_outline',(.65,.68,.71))] + ([('issued_card_reference',(0.97,0.97,0.98))] if CARD_ENABLED else []):
        assembly.add(refs[name],name=name,color=cq.Color(*col))
    assembly.save(str(OUT/'portrait_assembly.step'))
    for name in ('panel','pcb_placeholder','battery_envelope','usb_outline','wire_keepout','ph_plug_keepout') + (('issued_card_reference',) if CARD_ENABLED else ()):
        cq.exporters.export(refs[name],str(OUT/f'reference_{name}.step'))
    render_shapes([(parts['front_frame'],'#263447'),(refs['panel'],'#eceadf')],OUT/'portrait_iso_front.png',f'P1.1 REV B | 66 x 109 x {FRONT-BACK:.1f}mm | 3.6 in six-color')
    exploded=[(parts['front_frame'].translate((0,0,12)),'#263447'),(refs['panel'].translate((0,0,6)),'#eceadf'),
              (refs['pcb_placeholder'],'#247753'),(refs['battery_envelope'],'#a6b2be'),
              (parts['back_cover'].translate((0,0,-12)),'#607080')]
    render_shapes(exploded,OUT/'portrait_exploded.png','P1 mechanical stack | PCB and battery are envelopes',elevation=32,azimuth=-62)
    if CARD_ENABLED:
        render_shapes([(parts['card_sleeve'],'#3d4b5e'),(refs['issued_card_reference'],'#edf1f5')],OUT/'portrait_card_sleeve.png','Superseded removable carrier',elevation=-55,azimuth=70)
    (OUT/'mechanical_dimensions.json').write_text(json.dumps({'canonical':C,'derived':result},indent=2)+'\n')
    print(json.dumps({'status':result['status'],'dimensions':result['dimensions_mm'],'parts':list(parts)},indent=2))

from c1_geometry import install as install_c1
install_c1(sys.modules[__name__])

if __name__=='__main__':main()
