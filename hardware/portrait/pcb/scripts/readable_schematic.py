"""Reproducible reviewable P36 hierarchy. Reads design.py; never changes PCB/netmap.
Run with --output-dir for staged review. Integration: generate(D, S, PCB).
"""
from pathlib import Path
import sys, math, uuid, argparse, importlib.util
ROOT_UUID='0f1a3f2e-badc-4e00-9a11-000000000001'
NS=uuid.UUID(ROOT_UUID)
def uid(s): return str(uuid.uuid5(NS,str(s)))
def q(s): return '"'+str(s).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
def snap(v): return round(round(v/1.27)*1.27,2)
class Drawing:
 def __init__(self,D,S,name,title):
  self.D,self.S,self.name,self.title=D,S,name,title
  self.id=uid(name);self.path='/'+ROOT_UUID+'/'+self.id
  self.lib={};self.items=[];self.pins={};self.used=set();self.parts={};self.count=0;self.junctions=set();self.labels=set();self.wire_segments=set()
 def ident(self,t): self.count+=1;return uid(self.name+':'+str(self.count)+':'+t)
 def put(self,ref,x,y,angle=0):
  part=next(p for p in self.D.PARTS if p.ref==ref);self.parts[ref]=part
  key=part.lib+':'+part.symbol
  if key not in self.lib:self.lib[key]=self.S.K.resolve_symbol(self.S.K.lib_tree(self.S.SYM_LIBS[part.lib]),part.symbol,key,strip_v10=False)
  pins=self.S.K.symbol_pins(self.lib[key]);x,y=snap(x),snap(y);a=math.radians(angle)
  for p in pins:
   if p['number'] in part.omit_pins:continue
   px=snap(x+p['x']*math.cos(a)-p['y']*math.sin(a));py=snap(y-p['x']*math.sin(a)-p['y']*math.cos(a))
   self.pins[(ref,p['number'])]=(px,py,(p['angle']+angle)%360,part.pins.get(p['number']))
  simple=part.lib in ('Device','Diode') and len(pins)==2
  if simple and angle in (0,180) and part.symbol in ('R','C','L','FerriteBead'):
   rx,ry,vx,vy=x+4,y-1.27,x+4,y+1.27;just=' (justify left)'
  else:
   yy=[self.pins[(ref,p['number'])][1] for p in pins if (ref,p['number']) in self.pins];rx,ry,vx,vy=x,min(yy)-3.81,x,max(yy)+3.81;just=''
  s=[f'(symbol (lib_id {q(key)}) (at {x} {y} {angle}) (unit 1) (exclude_from_sim no) (in_bom {"no" if self.D.exclude_from_bom(part) else "yes"}) (on_board yes) (dnp {"yes" if part.dnp else "no"}) (uuid {q(uid(ref))})',f'(property "Reference" {q(ref)} (at {snap(rx)} {snap(ry)} {90 if angle in (90,270) else 0}) (effects (font (size 1.27 1.27)){just}))',f'(property "Value" {q(part.value)} (at {snap(vx)} {snap(vy)} {90 if angle in (90,270) else 0}) (effects (font (size 1.0 1.0)){just}))']
  for k,v in [('Footprint',self.D.board_footprint_id(part)),('Datasheet',''),('Description',part.desc),('LCSC',part.lcsc)]:s.append(f'(property {q(k)} {q(v)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
  for p in pins:
   if p['number'] not in part.omit_pins:s.append(f'(pin {q(p["number"])} (uuid {q(uid(ref+":"+p["number"]))}))')
  s.append(f'(instances (project "badge" (path {q(self.path)} (reference {q(ref)}) (unit 1)))))')
  self.items.append('\n'.join(s));return self
 def point(self,p):
  if isinstance(p[0],str):return self.pins[(p[0],str(p[1]))][:2]
  return (snap(p[0]),snap(p[1]))
 def wire(self,a,b):
  a,b=self.point(a),self.point(b)
  if a==b:return
  if a[0]!=b[0] and a[1]!=b[1]:
   self.wire(a,(b[0],a[1]));self.wire((b[0],a[1]),b);return
  edge=tuple(sorted((a,b)))
  if edge in self.wire_segments:return
  self.wire_segments.add(edge)
  self.items.append(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {q(self.ident("wire"))}))')
 def dot(self,p):
  x,y=self.point(p)
  if (x,y) in self.junctions:return
  self.junctions.add((x,y));self.items.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid {q(self.ident("dot"))}))')
 def label(self,net,p,rot=0):
  self.labels.add(net)
  x,y=self.point(p);j='left' if rot in (0,90) else 'right'
  self.items.append(f'(global_label {q(net)} (shape input) (at {x} {y} {rot}) (fields_autoplaced yes) (effects (font (size 1.0 1.0)) (justify {j})) (uuid {q(self.ident(net))}) (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x} {y} 0) (effects (font (size 1.0 1.0)) (hide yes))))')
 def route(self,net,*points,label=False):
  for p in points:
   if isinstance(p[0],str):
    key=(p[0],str(p[1]));assert self.pins[key][3]==net,(key,self.pins[key],net);self.used.add(key)
  for a,b in zip(points,points[1:]):self.wire(a,b)
  if label:self.label(net,points[-1])
 def link(self,net,a,b,via=None,label=False):
  pa,pb=self.point(a),self.point(b)
  pts=[a]
  if via is not None:pts+=via
  elif pa[0]!=pb[0] and pa[1]!=pb[1]:pts.append((pb[0],pa[1]))
  pts.append(b);self.route(net,*pts,label=label)
 def text(self,s,x,y,size=1.5):self.items.append(f'(text {q(s)} (exclude_from_sim no) (at {snap(x)} {snap(y)} 0) (effects (font (size {size} {size})) (justify left bottom)) (uuid {q(self.ident("text"))}))')
 def finish(self):
  for key in sorted(self.used):
   net=self.pins[key][3]
   if net and net not in self.labels:self.label(net,key)
  seen=set()
  for key,(x,y,a,net) in self.pins.items():
   if key in self.used:continue
   if (x,y) in seen:continue
   seen.add((x,y))
   # Stacked hidden MCU power pins share the served physical location.
   if any(self.pins[k][:2]==(x,y) for k in self.used):continue
   if net:
    length=5.08;dx=-math.cos(math.radians(a))*length;dy=math.sin(math.radians(a))*length
    end=(snap(x+dx),snap(y+dy));self.wire((x,y),end);self.label(net,end,int((a+180)%360))
   else:self.items.append(f'(no_connect (at {x} {y}) (uuid {q(self.ident("nc"))}))')
 def save(self,directory):
  self.finish();s=[f'(kicad_sch (version 20250114) (generator "P36_readable") (generator_version "10.0") (uuid {q(self.id)}) (paper "A3")',f'(title_block (title {q(self.title)}) (date "2026-09-30") (rev "P36 prototype") (comment 1 "Generated from design.py; electrical net map preserved; NOT production release"))','(lib_symbols']
  s += [self.S.K.dumps(x) for x in self.lib.values()];s+=[')']+self.items+[')'];(directory/(self.name+'.kicad_sch')).write_text('\n'.join(s)+'\n')

def generate(D,S,directory):
 # PROJECT_PINNED_CONNECTOR_GUARD
 project_pcb=Path(__file__).resolve().parent.parent
 assert Path(D.__file__).resolve()==project_pcb/'scripts/design.py'
 for nickname in ('Connector','Connector_Generic'):
  source=(project_pcb/'lib/pinned-symbols'/f'{nickname}.kicad_sym').resolve()
  assert source.parent==(project_pcb/'lib/pinned-symbols').resolve()
  S.SYM_LIBS[nickname]=str(source)
 S.q=q
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
 P={p.ref:p for p in D.PARTS};made=[]
 # A3 page 2: readable analog power topology, each block has named interface rails.
 p=Drawing(D,S,'power','P36 / 02 - Battery, charger, load sharing and 3.3 V')
 p.text('USB / BATTERY LOAD SHARING',22,24,2.3)
 for r,x,y,a in [('D10',80,45,180),('Q10',120,70,180),('R20',145,90,0),('C30',175,75,0),('J2',45,110,0)]:p.put(r,x,y,a)
 p.route('VBUS',('D10','2'),(50.8,44.45),label=True)
 p.link('VSYS',('D10','1'),('Q10','2'),via=[(117.475,44.45),(117.475,64.77)])
 # Coordinate routes use exact pin locations to avoid off-grid near-misses.
 p.link('VSYS',('Q10','2'),('C30','1'));p.label('VSYS',('C30','1'))
 p.link('VBUS',('Q10','1'),('R20','1'));p.label('VBUS',('Q10','1'))
 p.label('VBAT',('Q10','3'));p.used.add(('Q10','3'))
 p.link('GND',('R20','2'),('C30','2'),via=[(p.point(('R20','2'))[0],105.41),(p.point(('C30','2'))[0],105.41)],label=True)
 p.text('Adafruit 1578: keyed PH pin 1 = GND, pin 2 = VBAT\n500 mAh protected pack; measure incoming polarity and dimensions',22,138,1.5)
 p.text('MCP73831 CHARGER / 100 mA NOMINAL',22,164,2.1)
 for r,x,y,a in [('U3',80,205,0),('R3',50,223,0),('C2',125,225,0),('R4',145,180,0),('D4',145,204,90)]:p.put(r,x,y,a)
 p.link('PROG',('U3','5'),('R3','1'))
 p.link('GND',('R3','2'),('U3','2'),via=[(p.point(('R3','2'))[0],246.38),(p.point(('U3','2'))[0],246.38)])
 p.link('GND',('U3','2'),('C2','2'),via=[(p.point(('U3','2'))[0],246.38),(p.point(('C2','2'))[0],246.38)],label=True)
 p.link('VBAT',('U3','3'),('C2','1'));p.label('VBAT',('C2','1'))
 p.link('LED_CHRG_A',('R4','2'),('D4','2'))
 p.link('CHRG_STAT',('U3','1'),('D4','1'),via=[(109.22,p.point(('U3','1'))[1]),(109.22,234.95),(p.point(('D4','1'))[0],234.95)])
 p.text('3.3 V REGULATOR',225,25,2.1)
 for r,x,y,a in [('U4',290,65,0),('C3',250,88,0),('C4',330,88,0)]:p.put(r,x,y,a)
 p.link('VSYS',('U4','1'),('U4','3'),via=[(270.51,p.point(('U4','1'))[1]),(270.51,p.point(('U4','3'))[1])])
 p.link('VSYS',('U4','1'),('C3','1'));p.label('VSYS',('C3','1'))
 p.link('+3V3',('U4','5'),('C4','1'));p.label('+3V3',('C4','1'))
 for r in ['C3','U4','C4']:p.route('GND',(r,'2'),(p.point((r,'2'))[0],114.3))
 p.route('GND',*[ (p.point((r,'2'))[0],114.3) for r in ['C3','U4','C4'] ],label=True)
 for x in [250.19,290.83,330.2]:p.dot((x,114.3))
 p.text('BATTERY / USB PRESENT ADC',190,164,2.1)
 for r,x,y in [('R22',185,195),('R23',185,225),('C32',220,225)]:p.put(r,x,y)
 p.link('VBUS_SENSE',('R22','2'),('R23','1'));p.link('VBUS_SENSE',('R23','1'),('C32','1'));p.label('VBUS_SENSE',('C32','1'))
 p.link('GND',('R23','2'),('C32','2'),label=True)
 for r,x,y,a in [('R5',265,195,0),('R6',265,225,0),('C5',310,225,0),('TP2',365,180,0),('TP3',365,205,0),('TP4',365,230,0)]:p.put(r,x,y,a)
 p.link('BAT_SENSE',('R5','2'),('R6','1'));p.link('BAT_SENSE',('R6','1'),('C5','1'));p.label('BAT_SENSE',('C5','1'))
 p.link('GND',('R6','2'),('C5','2'),label=True)
 p.text('No cell-temperature input: prototype charging only in controlled 0-45 C conditions.\nCharger thermal regulation protects its die, not the battery. Verify enclosure temperature.\nAt low VBAT, LDO dropout limits usable capacity; test simultaneous RF + refresh load.',220,150,1.4)
 made.append(p)
 # Page 3: both boost stages wired like vendor reference.
 b=Drawing(D,S,'boost','P36 / 03 - E6 positive and negative boost reference')
 b.text('POSITIVE BOOST + INVERTING CHARGE PUMP',22,24,2.2)
 for r,x,y,a in [('L1',70,55,90),('Q1',95,85,0),('R100',65,103,0),('R101',97.79,112,0),('D1',145,55,180),('R104',220,55,90),('C112',120,82,0),('D3',155,103,180),('D2',155,125,0),('C113',185,80,0),('C114',40,82,0),('C115',235,140,0)]:b.put(r,x,y,a)
 b.link('V_B',('L1','1'),('C114','1'));b.label('V_B',('C114','1'))
 b.link('SW_H',('L1','2'),('Q1','3'));b.link('SW_H',('Q1','3'),('D1','2'),via=[(b.point(('Q1','3'))[0],55.88)]);b.link('SW_H',('D1','2'),('C112','1'))
 b.link('VPH',('D1','1'),('R104','1'));b.link('VPH',('D1','1'),('C113','1'));b.label('VPH',('C113','1'))
 b.link('GDRH',('Q1','1'),('R100','1'));b.label('GDRH',('Q1','1'))
 b.link('RESEH',('Q1','2'),('R101','1'));b.label('RESEH',('R101','1'))
 b.link('PUMP_H',('C112','2'),('D3','2'),via=[(b.point(('C112','2'))[0],b.point(('D3','2'))[1])]);b.link('PUMP_H',('D3','2'),('D2','1'),via=[(137.16,b.point(('D3','2'))[1]),(137.16,b.point(('D2','1'))[1])])
 b.link('VGL',('D2','2'),('C115','1'));b.label('VGL',('C115','1'))
 # Ground returns explicit and intentionally separated from switching nodes.
 for r,pin in [('C114','2'),('R100','2'),('R101','2')]:b.route('GND',(r,pin),(b.point((r,pin))[0],146.05))
 b.route('GND',*[ (b.point((r,'2'))[0],146.05) for r in ['C114','R100','R101'] ],label=True)
 for r in ['C113','C115']:b.route('GND',(r,'2'),(b.point((r,'2'))[0],158.75))
 b.route('GND',('D3','1'),(208.28,b.point(('D3','1'))[1]),(208.28,158.75));b.route('GND',(185.42,158.75),(208.28,158.75),(234.95,158.75),label=True)
 b.text('NEGATIVE BOOST / P-MOS SOURCE TOWARD V_B',22,178,2.2)
 for r,x,y,a in [('Q2',95,215,180),('R102',130,202,0),('C122',55,220,0),('L2',92.71,240,0),('R103',92.71,265,0),('D6',160,230,0),('C125',205,249,0)]:b.put(r,x,y,a)
 b.link('V_B',('Q2','2'),('C122','1'),via=[(b.point(('Q2','2'))[0],190.5),(b.point(('C122','1'))[0],190.5)])
 b.link('V_B',('Q2','2'),('R102','2'),via=[(b.point(('Q2','2'))[0],190.5),(146.05,190.5),(146.05,b.point(('R102','2'))[1])]);b.label('V_B',('C122','1'))
 b.link('GDRC',('Q2','1'),('R102','1'),via=[(113.03,b.point(('Q2','1'))[1]),(113.03,b.point(('R102','1'))[1])]);b.label('GDRC',('Q2','1'))
 b.link('SW_C',('Q2','3'),('L2','1'));b.link('SW_C',('Q2','3'),('D6','1'));b.link('RESEC',('L2','2'),('R103','1'));b.label('RESEC',('R103','1'))
 b.label('SW_C',(120.65,219.71))
 b.link('VPC',('D6','2'),('C125','1'));b.label('VPC',('C125','1'))
 b.link('GND',('C122','2'),('R103','2'),via=[(b.point(('C122','2'))[0],274.32),(b.point(('R103','2'))[0],274.32)],label=True)
 b.text('Reference: Waveshare 3.6 E6 HAT+ schematic. Preserve 10 uH / 0.2 ohm values.\nScope boost rails, startup ripple, MOS drive and effective MLCC capacitance before qualification.\nV_B bulk reservoir and the separated logic ferrite branch are on the display sheet.',260,80,1.5)
 made.append(b)
 # USB+MCU interface sheet: no invisible virtual pin connections; wire stubs and named cross-sheet links.
 m=Drawing(D,S,'usb_mcu','P36 / 01 - USB-C, ESD and ESP32-C3')
 m.text('USB-C DEVICE / CC PULLDOWNS',22,24,2.2)
 for r,x,y,a in [('J3',45,65,0),('R1',85,120,0),('R2',110,120,0),('C1',145,65,0),('U5',125,90,0)]:m.put(r,x,y,a)
 m.link('CC1',('J3','A5'),('R1','1'));m.link('CC2',('J3','B5'),('R2','1'))
 m.link('GND',('R1','2'),('R2','2'),label=True)
 m.link('USB_DN',('J3','A7'),('J3','B7'),via=[(71.12,m.point(('J3','A7'))[1]),(71.12,m.point(('J3','B7'))[1])])
 m.link('USB_DP',('J3','A6'),('J3','B6'),via=[(76.2,m.point(('J3','A6'))[1]),(76.2,m.point(('J3','B6'))[1])])
 m.label('USB_DN',('J3','B7'));m.label('USB_DP',('J3','B6'))
 m.text('MCU / E-PAPER HOST',205,24,2.2);m.put('U1',290,85)
 m.text('Antenna: physical copper/component keepout is defined on PCB.\nEPD BUSY is active low. Gate defaults OFF. Firmware must float SPI before power-off.',205,143,1.4)
 rem=[r for r,v in P.items() if v.section=='MCU' and r!='U1']
 for i,r in enumerate(rem):m.put(r,35+(i%6)*64,183+(i//6)*53)
 m.text('RESET, STRAPS, DECOUPLING AND STATUS',22,160,2.2);made.append(m)
 # Display: 50-pin pinout plus physically grouped supply and filter networks.
 d=Drawing(D,S,'display','P36 / 04 - E6 50-pin interface and rail filtering')
 d.text('3.6 INCH SPECTRA 6 / 400 x 600 PORTRAIT',22,24,2.2);d.put('J1',80,100)
 d.text('FH34SRJ-50S-0.5SH(50)\n50 pin / 0.5 mm / 0.3 mm FPC\nPin 1 and contact orientation: inspect real panel\nBS1 = 0, BS0 = 0: four-wire SPI\nOnly specified NC pins left open',22,205,1.5)
 used={r for sh in made for r in sh.parts}|{'J1'}
 rem=[r for r in P if r not in used]
 # Gates/inductors are kept separate from dense filter capacitor banks.
 for r,x,y,a in [('Q20',160,48,180),('FB1',220,70,90),('FB2',220,40,90),('C100',275,86,0),('C101',330,55,0)]:d.put(r,x,y,a)
 d.link('EPD_SUPPLY',('Q20','3'),('FB1','1'),via=[(190.5,d.point(('Q20','3'))[1]),(190.5,d.point(('FB1','1'))[1])])
 d.link('EPD_SUPPLY',('FB1','1'),('FB2','1'),via=[(190.5,d.point(('FB1','1'))[1]),(190.5,d.point(('FB2','1'))[1])])
 d.label('EPD_SUPPLY',(190.5,69.85))
 d.link('V_B',('FB1','2'),('C100','1'));d.label('V_B',('C100','1'))
 d.link('EPD_3V3',('FB2','2'),('C101','1'));d.label('EPD_3V3',('C101','1'))
 rem=[r for r in rem if r not in d.parts]
 for i,r in enumerate(rem):d.put(r,150+(i%5)*50,120+(i//5)*35)
 for row in range((len(rem)+4)//5):
  rr=[r for r in rem[row*5:row*5+5] if P[r].pins.get('2')=='GND']
  if not rr:continue
  yy=snap(120+row*35+14)
  for r in rr:d.route('GND',(r,'2'),(d.point((r,'2'))[0],yy))
  pts=[(d.point((r,'2'))[0],yy) for r in rr]
  d.route('GND',*pts,label=True)
 d.text('All boost capacitors retain vendor voltage ratings.\nMLCC nominal capacitance is not its capacitance under DC bias.\nNo universal door-access electronics: authorised internal credential remains system-dependent.',22,253,1.4)
 made.append(d)
 assert set(P)=={r for sh in made for r in sh.parts},set(P)-{r for sh in made for r in sh.parts}
 # Power flags live on root and reference rails globally.
 root=S.Sheet();root.text('P36 | SIX-COLOR PORTRAIT BADGE',20,23,3)
 root.text('Engineering prototype - not a production release',20,33,1.8)
 titles=[('usb_mcu','01  USB-C + MCU'),('power','02  BATTERY + POWER'),('boost','03  DUAL BOOST'),('display','04  DISPLAY + FILTERS')]
 for i,(name,title) in enumerate(titles):
  x,y=25+(i%2)*140,60+(i//2)*65;sid=uid(name)
  root.items.append(f'(sheet (at {x} {y}) (size 115 40) (stroke (width 0.2) (type default)) (fill (color 0 0 0 0)) (uuid {q(sid)}) (property "Sheetname" {q(title)} (at {x} {y-2} 0) (effects (font (size 1.8 1.8)) (justify left bottom))) (property "Sheetfile" {q(name+".kicad_sch")} (at {x} {y+42} 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project "badge" (path {q("/"+ROOT_UUID)} (page {q(i+2)})))))')
 root.text('Start with POWER and BOOST for electrical review.\nCross-sheet rails and MCU signals use global labels.\nNo external card sleeve. Internal authorised access inlay is pending system identification.\nMeasurements still required: refresh/USB/battery/RF/ESD/thermal/mechanical validation.',25,205,1.6)
 flag=root.add_lib_symbol('power','PWR_FLAG')
 for i,net in enumerate(D.PWR_FLAG_NETS):root.place_symbol(D.Part(f'#FLG0{i+1}','power','PWR_FLAG','','PWR_FLAG',{'1':net}),snap(30+i*60),snap(242),flag)
 master=[f'(kicad_sch (version 20250114) (generator "P36_readable") (generator_version "10.0") (uuid {q(ROOT_UUID)}) (paper "A3")','(title_block (title "P36 - Engineering review hierarchy") (date "2026-09-30") (rev "P36 prototype"))','(lib_symbols']+[S.K.dumps(x) for x in root.lib_symbols.values()]+[')']+root.items+['(sheet_instances (path "/" (page "1")))',')']
 for sh in made:sh.save(directory)
 (directory/'badge.kicad_sch').write_text('\n'.join(master)+'\n')
 return [directory/'badge.kicad_sch']+[directory/(s.name+'.kicad_sch') for s in made]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output-dir',required=True);args=ap.parse_args()
 here=Path(__file__).resolve().parent;sys.path.insert(0,str(here));import design as D
 base=here.parents[3]/'hardware/pcb/scripts';sys.path.insert(1,str(base));import gen_schematic as S
 S.D=D;S.STRIP_V10=False;pcb=here.parent;S.SYM_LIBS['Espressif']=str(pcb/'lib/Espressif.kicad_sym');S.SYM_LIBS['Badge']=str(pcb/'lib/badge.kicad_sym');S.SYM_LIBS['Power_Protection']=str(pcb/'lib/pinned-symbols/Power_Protection.kicad_sym')
 for p in generate(D,S,args.output_dir):print(p)
if __name__=='__main__':main()
