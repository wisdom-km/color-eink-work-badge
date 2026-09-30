"""Visible P36 final audit. Never regenerates PCB. Only footprint paths may change."""
from pathlib import Path
from datetime import datetime, timezone
import sys, os, json, re, shutil, hashlib, subprocess, importlib.util
import xml.etree.ElementTree as ET
W=Path('/workspace/scratch/200245c5fbc3')
R=W/'chroma-badge'; P=R/'hardware/portrait/pcb'; B=P/'badge.kicad_pcb'
CLI=W/'toolchain/bin/kicad-cli'
sys.path.insert(0,str(W/'toolchain/pcb-python'))
import sexpdata as SX
O=R/'verification/visible-final'
O.mkdir(parents=True,exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
backup=O/('backup-'+stamp);backup.mkdir()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def tag(x): return str(x[0]) if isinstance(x,list) and x else ''
def child(x,name):
    a=[v for v in x if tag(v)==name];assert len(a)==1,(name,len(a));return a[0]
def snapshot():
    paths=[B,P/'badge.kicad_pro',P/'scripts/design.py',P/'scripts/readable_schematic.py',P/'scripts/generate.py']
    paths+=list(P.glob('*.kicad_sch'))
    paths+=[P/'lib/pinned-symbols/Connector.kicad_sym',P/'lib/pinned-symbols/Connector_Generic.kicad_sym']
    return {str(p.relative_to(R)):sha(p) for p in sorted(paths)}
home=O/'cli-home'
for name in ('config','cache','data'): (home/name).mkdir(parents=True,exist_ok=True)
env=dict(os.environ)
env.update(HOME=str(home),XDG_CONFIG_HOME=str(home/'config'),XDG_CACHE_HOME=str(home/'cache'),XDG_DATA_HOME=str(home/'data'))
execution=[]
def run(args):
    args=list(map(str,args));before=snapshot()
    print('\nVISIBLE RUN:', ' '.join(args),flush=True)
    result=subprocess.run(args,cwd=R,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    print(result.stdout,flush=True)
    after=snapshot()
    execution.append({'command':args,'returncode':result.returncode,'stdout':result.stdout,'before':before,'after':after})
    (O/'execution-sha-log.json').write_text(json.dumps(execution,indent=2))
    assert before==after,'CLI unexpectedly changed source or board'
    assert result.returncode==0,result.returncode
    return result.stdout
assert subprocess.check_output([str(CLI),'version'],env=env,text=True).strip().startswith('10.')
source_before=snapshot();(O/'source-before.json').write_text(json.dumps(source_before,indent=2))
board_before=sha(B);board_after=board_before;bt=SX.loads(B.read_text())
counts={t:sum(tag(a)==t for a in bt) for t in ('footprint','segment','via','zone')}
assert counts['footprint']==81 and counts['segment']==968 and counts['via']==115
clean=lambda root:root
spec=importlib.util.spec_from_file_location('p36_final_source',P/'scripts/design.py')
D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
parts={p.ref:p for p in D.PARTS};assert len(parts)==81
run([CLI,'sch','export','netlist','--format','kicadxml','-o',O/'netlist.xml',P/'badge.kicad_sch'])
run([CLI,'sch','erc','--format','json','--severity-all','-o',O/'erc.json',P/'badge.kicad_sch'])
run([CLI,'sch','erc','--severity-all','-o',O/'erc.rpt',P/'badge.kicad_sch'])
run([CLI,'pcb','drc','--schematic-parity','--all-track-errors','--refill-zones','--format','json','-o',O/'drc.json',B])
run([CLI,'pcb','drc','--schematic-parity','--all-track-errors','--refill-zones','-o',O/'drc.rpt',B])
run([CLI,'sch','export','pdf','-o',O/'schematic-review.pdf',P/'badge.kicad_sch'])
want={(p.ref,str(k)):v for p in D.PARTS for k,v in p.pins.items()}
nc={(p.ref,str(k)):D.nc_unconnected_net(p.ref,str(k)) for p in D.PARTS for k in p.nc if str(k) not in p.omit_pins}
assert len(want)==259 and len(nc)==28
xml=ET.parse(O/'netlist.xml').getroot();got={}
refs={a.get('ref') for a in xml.findall('./components/comp') if not a.get('ref','').startswith('#')};assert refs==set(parts)
for n in xml.findall('./nets/net'):
    for node in n.findall('node'):
        key=(node.get('ref'),node.get('pin'))
        if key[0] in parts:assert key not in got;got[key]=n.get('name')
key=('U1','19');raw='unconnected-(U1-GPIO5{slash}ADC2_CH0-Pad19)';plain='unconnected-(U1-GPIO5/ADC2_CH0-Pad19)'
assert nc[key]==raw and key not in want
if got.get(key)==plain:
    nn=[n for n in xml.findall('./nets/net') if n.get('name')==plain];assert len(nn)==1
    nodes=nn[0].findall('node');assert len(nodes)==1 and (nodes[0].get('ref'),nodes[0].get('pin'))==key and 'no_connect' in nodes[0].get('pintype','')
    got[key]=raw
expected={**want,**nc};errors=[(k,v,got.get(k)) for k,v in expected.items() if got.get(k)!=v]
assert not (set(got)-set(expected))
(O/'net-parity.json').write_text(json.dumps({'parts':81,'connected_pins':259,'nc_pins':28,'errors':errors,'nc_alias':'only isolated U1/19 slash serialization'},indent=2))
assert not errors,errors
assert sha(B)==board_after and clean(SX.loads(B.read_text()))==clean(bt)
def findings(path):
    text=path.read_text();return {'types':re.findall(r'^\[([^\]]+)\]:',text,re.M),'errors':len(re.findall(r'; error',text)),'warnings':len(re.findall(r'; warning',text)),'ignored_tail':text.split('** Ignored checks:')[-1].strip() if '** Ignored checks:' in text else ''}
erc_result=findings(O/'erc.rpt');drc_result=findings(O/'drc.rpt')
result={'status':'REVIEW_WARNINGS' if erc_result['warnings'] or drc_result['warnings'] else 'PASS','board_before':board_before,'board_after':board_after,'only_board_change':'none during audit; prior controlled paths and 3 switch descriptions','board_counts':counts,'net_parity':'81/259/28 exact','erc':erc_result,'drc':drc_result,'backup':str(backup),'source_after':snapshot()}
(O/'result.json').write_text(json.dumps(result,indent=2));(O/'source-after.json').write_text(json.dumps(snapshot(),indent=2))
print(json.dumps(result,indent=2),flush=True)
assert erc_result['ignored_tail'] in ('','- None'),'ERC ignored checks remain'
assert not erc_result['errors'] and not drc_result['errors'],'Actual errors require review'
print('FINISHED. Inspect all warnings in full reports; no checks hidden.',flush=True)
