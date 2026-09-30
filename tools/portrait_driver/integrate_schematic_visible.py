from pathlib import Path
from datetime import datetime, timezone
import os, sys, re, json, shutil, hashlib, subprocess, importlib.util
import xml.etree.ElementTree as ET
WORK=Path('/workspace/scratch/200245c5fbc3')
REPO=WORK/'chroma-badge'
PCB=REPO/'hardware/portrait/pcb'
SCRIPTS=PCB/'scripts'; LIB=PCB/'lib/pinned-symbols'; BOARD=PCB/'badge.kicad_pcb'
CLI=WORK/'toolchain/bin/kicad-cli'; PYLIB=WORK/'toolchain/pcb-python'
STAMP=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
BACKUP=PCB/('integration-backup-'+STAMP); OUT=PCB/('integration-check-'+STAMP)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require_inside(path,base):
    assert path.resolve().is_relative_to(base.resolve()),str(path)
    assert not path.is_symlink(),'Refusing symlink: '+str(path)
def run(args,env):
    args=[str(a) for a in args]
    print('\nRUN:',' '.join(args),flush=True)
    subprocess.run(args,cwd=REPO,env=env,check=True,timeout=240)
assert REPO.is_dir() and CLI.is_file() and BOARD.is_file()
assert (SCRIPTS/'readable_schematic.py').is_file()
assert str(LIB.resolve())==str(LIB)
for name in ('Connector.kicad_sym','Connector_Generic.kicad_sym'): require_inside(LIB/name,LIB)
names=['badge.kicad_sch','power.kicad_sch','boost.kicad_sch','usb_mcu.kicad_sch','display.kicad_sch']
affected=[SCRIPTS/'design.py',SCRIPTS/'generate.py',SCRIPTS/'readable_schematic.py',LIB/'Connector.kicad_sym',LIB/'Connector_Generic.kicad_sym']+[PCB/n for n in names]
BACKUP.mkdir(exist_ok=False); OUT.mkdir(exist_ok=False)
original={}
for path in affected:
    require_inside(path,PCB)
    original[str(path.relative_to(PCB))]=sha(path) if path.exists() else None
    if path.exists():
        dest=BACKUP/path.relative_to(PCB); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dest)
shutil.copy2(BOARD,BACKUP/BOARD.name); board_before=sha(BOARD)
(BACKUP/'manifest.json').write_text(json.dumps({'files':original,'board_sha256':board_before},indent=2))
print('Backup:',BACKUP,flush=True); print('Routed PCB SHA256:',board_before,flush=True)
try:
    changes={'Connector_Generic.kicad_sym':{'Conn_01x50':'badge:FH34SRJ-50S-0.5SH','Conn_01x02':'Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal'},'Connector.kicad_sym':{'USB_C_Receptacle_USB2.0_16P':'badge:TYPE-C-31-M-14'}}
    prepared={}
    for filename,mapping in changes.items():
        path=LIB/filename; text=path.read_text()
        for symbol,footprint in mapping.items():
            pattern=r'(\(symbol\s+"'+re.escape(symbol)+r'"\s+(?:(?!\(symbol).)*?\(property\s+"ki_fp_filters"\s+")([^"]*)(")'
            matches=list(re.finditer(pattern,text,re.S)); assert len(matches)==1,(filename,symbol,len(matches))
            match=matches[0]; print('FILTER:',symbol,match.group(2),'->',footprint,flush=True)
            text=text[:match.start(2)]+footprint+text[match.end(2):]
        prepared[path]=text
    for path,text in prepared.items(): path.write_text(text)
    path=SCRIPTS/'design.py'; text=path.read_text()
    start='# BEGIN VISIBLE_FINAL_SOURCE_SYNC'; end='# END VISIBLE_FINAL_SOURCE_SYNC'
    assert text.count(start)==text.count(end) and text.count(start)<=1
    if start in text: text=text[:text.index(start)]+text[text.index(end)+len(end):]
    text+='''
# BEGIN VISIBLE_FINAL_SOURCE_SYNC
for _ref, _at in {
    'R1': (44.2, 83.85, 90),
    'R2': (55.5, 83.85, 90),
    'R21': (14.5, 60.1, 90),
    'SW3': (3, 46, 0),
}.items():
    next(p for p in PARTS if p.ref == _ref).at = _at
assert NET_CLASSES['Power']['track'] == 0.4
NET_CLASSES['Power']['nets'] = [n for n in NET_CLASSES['Power']['nets'] if n != 'RESEC']
NET_CLASSES['Sense'] = {'clearance': 0.2, 'track': 0.2, 'via': 0.6, 'via_drill': 0.3, 'nets': ['RESEC']}
# END VISIBLE_FINAL_SOURCE_SYNC
'''
    path.write_text(text)
    path=SCRIPTS/'generate.py'; text=path.read_text()
    old='if "--pcb-only" not in sys.argv: S.main()'
    new='if "--pcb-only" not in sys.argv:\n'+"    load('p36_readable', HERE/'readable_schematic.py').generate(D, S, PCB)"
    assert text.count(old)==1 or new in text,'Unexpected generate.py entry point'
    if old in text: text=text.replace(old,new,1)
    path.write_text(text)
    path=SCRIPTS/'readable_schematic.py'; text=path.read_text(); marker='# PROJECT_PINNED_CONNECTOR_GUARD'
    if marker not in text:
        anchor='def generate(D,S,directory):\n'; assert text.count(anchor)==1
        guard=''' # PROJECT_PINNED_CONNECTOR_GUARD
 project_pcb=Path(__file__).resolve().parent.parent
 assert Path(D.__file__).resolve()==project_pcb/'scripts/design.py'
 for nickname in ('Connector','Connector_Generic'):
  source=(project_pcb/'lib/pinned-symbols'/f'{nickname}.kicad_sym').resolve()
  assert source.parent==(project_pcb/'lib/pinned-symbols').resolve()
  S.SYM_LIBS[nickname]=str(source)
'''
        text=text.replace(anchor,anchor+guard,1)
    path.write_text(text)
    env=dict(os.environ); env['PYTHONPATH']=str(PYLIB)+os.pathsep+env.get('PYTHONPATH','')
    home=OUT/'kicad-home'
    for name in ('cache','config','data'): (home/name).mkdir(parents=True,exist_ok=True)
    env.update(HOME=str(home),XDG_CACHE_HOME=str(home/'cache'),XDG_CONFIG_HOME=str(home/'config'),XDG_DATA_HOME=str(home/'data'))
    version=subprocess.check_output([str(CLI),'version'],cwd=REPO,env=env,text=True).strip(); assert version.startswith('10.'),version
    print('KiCad:',version,flush=True)
    run([sys.executable,SCRIPTS/'readable_schematic.py','--output-dir',PCB],env)
    assert sha(BOARD)==board_before,'PCB changed while generating schematic'
    for name in names: assert (PCB/name).is_file() and (PCB/name).stat().st_size>100
    run([CLI,'sch','export','netlist','--format','kicadxml','-o',OUT/'netlist.xml',PCB/'badge.kicad_sch'],env)
    run([CLI,'sch','erc','-o',OUT/'erc.rpt',PCB/'badge.kicad_sch'],env)
    run([CLI,'sch','export','pdf','-o',OUT/'review.pdf',PCB/'badge.kicad_sch'],env)
    spec=importlib.util.spec_from_file_location('p36_integration_source',SCRIPTS/'design.py')
    D=importlib.util.module_from_spec(spec); sys.modules[spec.name]=D; spec.loader.exec_module(D)
    parts={p.ref:p for p in D.PARTS}; assert len(parts)==len(D.PARTS)==81
    expected={(p.ref,str(pin)):net for p in D.PARTS for pin,net in p.pins.items()}
    assert len(expected)==259,('Connected pin count changed',len(expected))
    expected_nc={(p.ref,str(pin)):D.nc_unconnected_net(p.ref,str(pin)) for p in D.PARTS for pin in p.nc if str(pin) not in p.omit_pins}
    tree=ET.parse(OUT/'netlist.xml').getroot()
    exported_refs={x.get('ref') for x in tree.findall('./components/comp') if not x.get('ref','').startswith('#')}
    assert exported_refs==set(parts),('Component mismatch',exported_refs^set(parts))
    actual={}
    for net in tree.findall('./nets/net'):
        for node in net.findall('node'):
            key=(node.get('ref'),node.get('pin'))
            if key[0] not in parts: continue
            assert key not in actual,('Duplicate exported pin',key)
            actual[key]=net.get('name')
    # EXACT_KICAD_NC_SLASH_ALIAS: serialization only; retain source and PCB spelling.
    alias_key=('U1','19')
    source_nc='unconnected-(U1-GPIO5{slash}ADC2_CH0-Pad19)'
    xml_nc='unconnected-(U1-GPIO5/ADC2_CH0-Pad19)'
    assert expected_nc.get(alias_key)==source_nc and alias_key not in expected
    if actual.get(alias_key)==xml_nc:
        matches=[n for n in tree.findall('./nets/net') if n.get('name')==xml_nc]
        assert len(matches)==1
        nodes=matches[0].findall('node')
        assert len(nodes)==1
        assert (nodes[0].get('ref'),nodes[0].get('pin'))==alias_key
        assert 'no_connect' in nodes[0].get('pintype','')
        actual[alias_key]=source_nc
        print('Normalized only U1/19 NC slash serialization; verified isolated no-connect node',flush=True)
    errors=[]
    for key,net in {**expected,**expected_nc}.items():
        if actual.get(key)!=net: errors.append((key,net,actual.get(key)))
    extra=set(actual)-set(expected)-set(expected_nc)
    if extra: errors.append(('Unexpected exported pins',sorted(extra)))
    (OUT/'pin-parity.json').write_text(json.dumps({'parts':len(parts),'connected_pins':len(expected),'nc_pins':len(expected_nc),'errors':errors},indent=2))
    assert not errors,json.dumps(errors,indent=2)
    erc=(OUT/'erc.rpt').read_text(); violation_types=re.findall(r'^\[([^\]]+)\]:',erc,re.M)
    assert not violation_types,('ERC violations',violation_types)
    assert sha(BOARD)==board_before,'PCB changed during verification'
    sys.path.insert(0,str(PYLIB)); import sexpdata as SX
    def tag(node): return str(node[0]) if isinstance(node,list) and node else ''
    def child(node,name):
        found=[x for x in node if tag(x)==name]; assert len(found)==1,(name,len(found)); return found[0]
    links={}
    for filename in names[1:]:
        document=SX.loads((PCB/filename).read_text())
        for symbol in document:
            if tag(symbol)!='symbol': continue
            reference=next(x[2] for x in symbol if tag(x)=='property' and x[1]=='Reference')
            if reference not in parts: continue
            symbol_uuid=str(child(symbol,'uuid')[1]); instance=child(child(child(symbol,'instances'),'project'),'path')
            links[reference]={'path':str(instance[1])+'/'+symbol_uuid,'sheetfile':filename}
    assert set(links)==set(parts)
    (OUT/'schematic-links.json').write_text(json.dumps(links,indent=2))
    (OUT/'result.json').write_text(json.dumps({'status':'PASS','parts':81,'connected_pins':259,'nc_pins':len(expected_nc),'erc_violations':0,'board_before':board_before,'board_after':sha(BOARD),'board_modified':False,'backup':str(BACKUP)},indent=2))
    print('\nPASS: five native sheets; 81 parts; 259 connected pins; exact NC parity; ERC 0.',flush=True)
    print('PCB byte-identical. Review PDF and exact link map:',OUT,flush=True)
    print('NEXT: visible KiCad 10 relink by reference only; require 0 added/0 deleted footprints.',flush=True)
    print('Do not replace footprints, move items, regenerate board, or change copper. Then run full schematic-parity DRC.',flush=True)
except Exception:
    print('\nFAILED: restoring only files this script owned; routed PCB is not overwritten.',flush=True)
    for relative,digest in original.items():
        path=PCB/relative; saved=BACKUP/relative
        if digest is None:
            if path.exists(): path.unlink()
        else:
            shutil.copy2(saved,path); assert sha(path)==digest
    print('PCB current SHA256:',sha(BOARD),flush=True)
    print('PCB original SHA256:',board_before,flush=True)
    print('Failure reports remain in:',OUT,flush=True)
    raise
