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
for path in (B,P/'badge.kicad_pro'):shutil.copy2(path,backup/path.name)
original=B.read_text();board_before=sha(B)
assert board_before=='43d6616a6cdcbe227db6de54ea461929b29e5b5dafca83bd37e3f66c64324570',board_before
spec=importlib.util.spec_from_file_location('p36_final_source',P/'scripts/design.py')
D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
parts={p.ref:p for p in D.PARTS};assert len(parts)==81
links={}
for filename in ('usb_mcu.kicad_sch','power.kicad_sch','boost.kicad_sch','display.kicad_sch'):
    doc=SX.loads((P/filename).read_text())
    for s in doc:
        if tag(s)!='symbol':continue
        ref=next(a[2] for a in s if tag(a)=='property' and a[1]=='Reference')
        if ref not in parts:continue
        ip=child(child(child(s,'instances'),'project'),'path')
        links[ref]=str(ip[1])+'/'+str(child(s,'uuid')[1])
assert set(links)==set(parts)
(O/'schematic-links.json').write_text(json.dumps(links,indent=2))
def spans(text):
    depth=0;quoted=False;escaped=False;start=None;out=[]
    for i,c in enumerate(text):
        if quoted:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
            continue
        if c=='"':quoted=True;continue
        if c=='(':
            if depth==1:start=i
            depth+=1
        elif c==')':
            depth-=1;assert depth>=0
            if depth==1 and start is not None:out.append((start,i+1));start=None
    assert depth==0 and not quoted
    return out
bt=SX.loads(original)
counts={t:sum(tag(a)==t for a in bt) for t in ('footprint','segment','via','zone')}
assert counts['footprint']==81 and counts['segment']==968 and counts['via']==115,counts
print('Before association:',counts,'SHA',board_before,flush=True)
replacements=[];seen=set()
for start,end in spans(original):
    block=original[start:end]
    if not re.match(r'\(footprint\s',block):continue
    fp=SX.loads(block)
    ref=next(a[2] for a in fp if tag(a)=='property' and a[1]=='Reference')
    assert ref in links and ref not in seen;seen.add(ref)
    existing=[(a,b) for a,b in spans(block) if re.match(r'\(path\s',block[a:b])]
    assert len(existing)<=1
    modified=block
    for a,b in reversed(existing):modified=modified[:a]+modified[b:]
    close=modified.rfind(')')
    modified=modified[:close]+'\n\t\t(path '+json.dumps(links[ref])+')\n\t'+modified[close:]
    assert [a for a in SX.loads(modified) if tag(a)!='path']==[a for a in fp if tag(a)!='path']
    replacements.append((start,end,modified))
assert seen==set(parts)
updated=original
for start,end,new in reversed(replacements):updated=updated[:start]+new+updated[end:]
def clean(root):return [[v for v in a if tag(v)!='path'] if tag(a)=='footprint' else a for a in root]
assert clean(SX.loads(updated))==clean(bt),'Unexpected non-path board change'
assert sha(B)==board_before,'Concurrent board change'
B.write_text(updated)
assert clean(SX.loads(B.read_text()))==clean(bt)
board_after=sha(B)
print('ASSOCIATED: 81 footprint paths only; all other board semantics identical. SHA',board_after,flush=True)
project=P/'badge.kicad_pro';jd=json.loads(project.read_text());erc=jd.setdefault('erc',{})
assert not erc.get('erc_exclusions',[]),'Existing ERC exclusions require review'
severities=erc.setdefault('rule_severities',{})
for key,value in list(severities.items()):
    if value=='ignore':severities[key]='warning'
for key in ('single_global_label','four_way_junction','simulation_model_issue','footprint_filter'):severities[key]='warning'
erc['erc_exclusions']=[]
project.write_text(json.dumps(jd,indent=2)+'\n')
print('All four default ignored ERC checks enabled as warnings; no ERC exclusions.',flush=True)
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
result={'status':'REVIEW_WARNINGS' if erc_result['warnings'] or drc_result['warnings'] else 'PASS','board_before':board_before,'board_after':board_after,'only_board_change':'81 schematic paths','board_counts':counts,'net_parity':'81/259/28 exact','erc':erc_result,'drc':drc_result,'backup':str(backup),'source_after':snapshot()}
(O/'result.json').write_text(json.dumps(result,indent=2));(O/'source-after.json').write_text(json.dumps(snapshot(),indent=2))
print(json.dumps(result,indent=2),flush=True)
assert not erc_result['ignored_tail'],'ERC ignored checks remain'
assert not erc_result['errors'] and not drc_result['errors'],'Actual errors require review'
print('FINISHED. Inspect all warnings in full reports; no checks hidden.',flush=True)
