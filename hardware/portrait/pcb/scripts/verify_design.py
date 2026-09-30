"""Compare generated schematic + PCB nets against P36 source, without mutating files."""
import sys,json,xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew
sys.path.insert(0,str(Path(__file__).resolve().parent));import design as D
PCB=Path(__file__).resolve().parents[1];OUT=PCB.parent/'verification';OUT.mkdir(exist_ok=True)
b=pcbnew.LoadBoard(str(PCB/'badge.kicad_pcb'));fps={x.GetReference():x for x in b.GetFootprints()};issues=[]
for p in D.PARTS:
 if p.ref not in fps:issues.append('missing '+p.ref);continue
 pads={}
 for pad in fps[p.ref].Pads():pads.setdefault(pad.GetNumber(),[]).append(pad.GetNetname().lstrip('/'))
 for pin,net in p.pins.items():
  if not pads.get(pin) or any(n!=net for n in pads[pin]):issues.append(f'{p.ref}.{pin} expected{net},actual{pads.get(pin)}')
 for pin in p.nc:
  if any(n and not n.startswith('unconnected-') for n in pads.get(pin,[])):issues.append(f'NC connected {p.ref}.{pin}')
source={p.ref:p for p in D.PARTS}
assert source['J1'].footprint=='badge:FH34SRJ-50S-0.5SH'
assert set(source['J1'].pins)|set(source['J1'].nc)=={str(i) for i in range(1,51)}
assert source['J1'].pins['26']==source['J1'].pins['27']=='GND' #4wireSPI
assert source['Q2'].pins=={'1':'GDRC','2':'V_B','3':'SW_C'}
assert source['Q10'].pins=={'1':'VBUS','2':'VSYS','3':'VBAT'}
assert source['U3'].value=='MCP73831T-2ACI/OT' and source['R3'].value=='10k'
# Read actual fresh exported netlist, including all connector supply pins.
netfile=OUT/'p36.net'
if netfile.exists():
 root=ET.parse(netfile).getroot();actual={}
 for net in root.findall('./nets/net'):
  for node in net.findall('node'):actual[(node.attrib['ref'],node.attrib['pin'])]=net.attrib['name'].lstrip('/')
 for p in D.PARTS:
  for pin,net in p.pins.items():
   if actual.get((p.ref,pin))!=net:issues.append(f'schematic {p.ref}.{pin}: {actual.get((p.ref,pin))} != {net}')
else:issues.append('fresh schematic netlist missing; export first')
tracks=list(b.GetTracks())
data={'parts':len(fps),'expected_parts':len(D.PARTS),'segments':sum(t.GetClass()=='PCB_TRACK' for t in tracks),'vias':sum(t.GetClass()=='PCB_VIA' for t in tracks),'panel_signal_pads':50,'board_size_mm':[D.BOARD_W,D.BOARD_H],'thickness_mm':D.BOARD_THICKNESS,'net_assignment_issues':issues,'checks':'source/schematic/PCB pin agreement, full50pins, SPIstraps, boostPMOS, loadsharingPMOS, chargerprogram','not_checked':['analog correctness by simulation','actual HVlevels','electrical/EMC/RF/ESD hardware tests','finished routing depends on separate DRC report']}
(OUT/'p36_net_consistency.json').write_text(json.dumps(data,indent=2));print(json.dumps(data));raise SystemExit(bool(issues))
