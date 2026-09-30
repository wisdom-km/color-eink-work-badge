"""Generate only P36 candidate. Never writes H2 board/schematic."""
from pathlib import Path
import sys,importlib.util,json
HERE=Path(__file__).resolve().parent;PCB=HERE.parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE));import design as D
BASE=ROOT/'hardware/pcb/scripts'
sys.path.insert(1,str(BASE))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
# Source: Hirose EDC-159714-50-08 p1/p4. Bottom insertion (+Y), pin1 right in top view.
f=['(footprint "FH34SRJ-50S-0.5SH" (version 20241229) (generator "P36") (layer "F.Cu")',
'(descr "Hirose FH34SRJ50 dual-contact .3FPC; EDC15971450 p1/p4; inspect pin1 vs panel before fab")',
'(attr smd)',
'(fp_text reference "J1" (at 0 -1.5) (layer "F.SilkS") (effects (font (size .8 .8) (thickness .12))))',
'(fp_text value "FH34SRJ-50S-0.5SH" (at 0 5) (layer "F.Fab") (effects (font (size .8 .8) (thickness .12))))',
'(fp_rect (start -13.5 -.15) (end 13.5 3.65) (stroke (width .1) (type default)) (fill none) (layer "F.Fab"))',
'(fp_rect (start -13.8 -.7) (end 13.8 4.1) (stroke (width .05) (type default)) (fill none) (layer "F.CrtYd"))',
'(fp_line (start 12 -1) (end 12.5 -1) (stroke (width .15) (type default)) (layer "F.SilkS"))']
for i in range(1,51):
 x=12.25-(i-1)*.5
 f.append(f'(pad "{i}" smd rect (at {x} 0) (size .3 .8) (layers "F.Cu" "F.Mask"))')
 f.append(f'(fp_rect (start {x-.125} -.4) (end {x+.125} .4) (stroke (width 0) (type default)) (fill solid) (layer "F.Paste"))')
for x in [-13.25,13.25]:f.append(f'(pad "" smd rect (at {x} 2.5) (size .4 .8) (layers "F.Cu" "F.Paste" "F.Mask"))')
f.append(')');(PCB/'lib/badge.pretty/FH34SRJ-50S-0.5SH.kicad_mod').write_text('\n'.join(f))
# Reuse proven generated-symbol serializer, changing output target and only P36 source.
S=load('p36_sch',BASE/'gen_schematic.py');S.D=D;S.PCB_DIR=str(PCB);S.OUT=str(PCB/'badge.kicad_sch');S.STRIP_V10=False
S.SYM_LIBS['Espressif']=str(PCB/'lib/Espressif.kicad_sym');S.SYM_LIBS['Badge']=str(PCB/'lib/badge.kicad_sym')
S.SYM_LIBS["Power_Protection"]=str(PCB/"lib/pinned-symbols/Power_Protection.kicad_sym")
if "--pcb-only" not in sys.argv:
    load('p36_readable', HERE/'readable_schematic.py').generate(D, S, PCB)
sch=(PCB/'badge.kicad_sch').read_text().replace('4.2\\" BWRY e-paper NFC badge','P36 six-color portrait badge PROTOTYPE').replace('(rev "v0.1")','(rev "P36-0.1-unreleased")')
(PCB/'badge.kicad_sch').write_text(sch)
import pcbnew
G=load('p36_pcb',BASE/'gen_pcb.py');G.D=D;G.PCB_DIR=str(PCB);G.OUT=str(PCB/'badge.kicad_pcb');G.OUT_DIR=str(PCB/'output')
class Candidate(G.Gen):
 def silkscreen(self):
  for text,x,y,size,thick in D.SILK_BACK:
   t=pcbnew.PCB_TEXT(self.board);t.SetText(text);t.SetPosition(G.P(x,y));t.SetLayer(pcbnew.B_SilkS);t.SetMirrored(True);t.SetTextSize(G.P(size,size));t.SetTextThickness(pcbnew.FromMM(thick));self.board.Add(t)
  # Hide refs initially; assembly drawing/BOM carries reference identifiers.
  for fp in self.fps.values():fp.Reference().SetVisible(False)
 def nfc_note(self):pass
 def zones(self):
  cu=[pcbnew.F_Cu,pcbnew.B_Cu]
  self.rule_area(D.ESP_ANT_KEEPOUT,cu,no_pour=True,no_tracks=True,no_vias=True,name='C3 antenna no-copper')
  self.rule_area(D.BATTERY_POCKET,[pcbnew.B_Cu],no_pour=False,no_footprints=True,name='Protected battery envelope no components')
  self.rule_area(D.WIRE_POCKET,[pcbnew.B_Cu],no_pour=False,no_footprints=True,name='Battery original lead loop no components')
  a,b,c,d=D.FPC_SLOT;self.rule_area((a-.6,b-.6,c+.6,d+.6),cu,no_pour=True,no_tracks=True,no_vias=True,name='FPC pass-through clearance')
  for x0,y0,x1,y1 in D.H.PORTRAIT['enclosure']['pcb_support_rects']:
   self.rule_area((x0,y0,x1,y1),[pcbnew.B_Cu],no_pour=False,no_footprints=True,name='Mechanical rear support contact')
  self.gnd_pour(pcbnew.F_Cu);self.gnd_pour(pcbnew.B_Cu)
g=Candidate()
for n in D.all_nets():g.net(n)
g.place_parts();g.apply_net_classes();g.outline();g.silkscreen();g.zones();g.fill();g.save();g.report()
# Emit reproducible BOM and candidate source inventory, not an order file.
import csv
with (PCB/'candidate_bom.csv').open('w') as out:
 w=csv.writer(out);w.writerow(['Reference','Value','Footprint','Description','DNP'])
 for p in D.PARTS:w.writerow([p.ref,p.value,p.footprint,p.desc,p.dnp])
