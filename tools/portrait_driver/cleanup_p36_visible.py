"""Visible cleanup: duplicate schematic wires, test-point BOM flags, three switch descriptions."""
from pathlib import Path
from datetime import datetime,timezone
import sys,os,json,re,shutil,hashlib,importlib.util,subprocess,runpy
W=Path('/workspace/scratch/200245c5fbc3');R=W/'chroma-badge';P=R/'hardware/portrait/pcb';B=P/'badge.kicad_pcb';O=R/'verification/visible-final'
sys.path.insert(0,str(W/'toolchain/pcb-python'))
import sexpdata as SX
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
backup=O/('cleanup-backup-'+stamp);backup.mkdir()
for f in list(O.iterdir()):
    if f.is_file():shutil.copy2(f,backup/f.name)
shutil.copy2(B,backup/B.name)
s=P/'scripts/readable_schematic.py';shutil.copy2(s,backup/s.name)
for f in P.glob('*.kicad_sch'):shutil.copy2(f,backup/f.name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
board_before=sha(B);assert board_before=='fa4446bebef2b3211d7aadf9aea0868279c5efdb3212abc343628df3a6942632'
text=s.read_text()
old='(in_bom yes)';new='(in_bom {"no" if self.D.exclude_from_bom(part) else "yes"})'
assert text.count(old)==1
text=text.replace(old,new,1)
old='self.junctions=set();self.labels=set()'
assert text.count(old)==1
text=text.replace(old,old+';self.wire_segments=set()',1)
old='  self.items.append(f\'(wire (pts'
assert text.count(old)==1
new='''  edge=tuple(sorted((a,b)))
  if edge in self.wire_segments:return
  self.wire_segments.add(edge)
'''+old
text=text.replace(old,new,1)
compile(text,str(s),'exec')
s.write_text(text)
print('Updated generator: preserves TP exclude-from-BOM and removes only identical wire segments.',flush=True)
env=dict(os.environ);env['PYTHONPATH']=str(W/'toolchain/pcb-python')+os.pathsep+env.get('PYTHONPATH','')
print('VISIBLE RUN: standalone readable_schematic.py',flush=True)
subprocess.run([sys.executable,str(s),'--output-dir',str(P)],cwd=R,env=env,check=True,timeout=240)
assert sha(B)==board_before
spec=importlib.util.spec_from_file_location('p36_desc_source',P/'scripts/design.py');D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
descriptions={p.ref:p.desc for p in D.PARTS if p.ref in ('SW1','SW2','SW3')};assert len(descriptions)==3
assert all('2.5mm' in v for v in descriptions.values())
def tag(x):return str(x[0]) if isinstance(x,list) and x else ''
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
original=B.read_text();tree=SX.loads(original);replacements=[]
for a,b in spans(original):
    block=original[a:b]
    if not re.match(r'\(footprint\s',block):continue
    fp=SX.loads(block);ref=next(x[2] for x in fp if tag(x)=='property' and x[1]=='Reference')
    if ref not in descriptions:continue
    matches=[]
    for c,d in spans(block):
        prop=SX.loads(block[c:d])
        if tag(prop)=='property' and prop[1]=='Description':matches.append((c,d,prop))
    assert len(matches)==1
    c,d,prop=matches[0];prop[2]=descriptions[ref]
    updated=block[:c]+SX.dumps(prop)+block[d:]
    replacements.append((a,b,updated));print('SW description synchronized:',ref,flush=True)
assert len(replacements)==3
updated=original
for a,b,block in reversed(replacements):updated=updated[:a]+block+updated[b:]
def strip_descriptions(root):
    result=[]
    for fp in root:
        if tag(fp)=='footprint':
            ref=next(x[2] for x in fp if tag(x)=='property' and x[1]=='Reference')
            if ref in descriptions:fp=[x for x in fp if not(tag(x)=='property' and x[1]=='Description')]
        result.append(fp)
    return result
assert strip_descriptions(SX.loads(updated))==strip_descriptions(tree)
assert sha(B)==board_before
B.write_text(updated)
assert strip_descriptions(SX.loads(B.read_text()))==strip_descriptions(tree)
(O/'cleanup-result.json').write_text(json.dumps({'board_before':board_before,'board_after':sha(B),'only_board_change':'SW1/SW2/SW3 Description; all other semantic data including paths and UUIDs identical','generator_changes':['TP in_bom follows source','deduplicate identical wire segments'],'backup':str(backup)},indent=2))
# Reuse the visible audited command runner, but OMIT all board/project mutation stages.
base=(R/'tools/portrait_driver/finalize_p36_visible.py').read_text()
prefix=base[:base.index('source_before=snapshot()')]
load_source=base[base.index('spec=importlib.util.spec_from_file_location'):base.index('links={}')] 
setup='''source_before=snapshot();(O/'source-before.json').write_text(json.dumps(source_before,indent=2))
board_before=sha(B);board_after=board_before;bt=SX.loads(B.read_text())
counts={t:sum(tag(a)==t for a in bt) for t in ('footprint','segment','via','zone')}
assert counts['footprint']==81 and counts['segment']==968 and counts['via']==115
clean=lambda root:root
'''
tail=base[base.index("run([CLI,'sch','export','netlist'"):]
tail=tail.replace("assert not erc_result['ignored_tail']", "assert erc_result['ignored_tail'] in ('','- None')")
tail=tail.replace("'only_board_change':'81 schematic paths'", "'only_board_change':'none during audit; prior controlled paths and 3 switch descriptions'",1)
audit=prefix+setup+load_source+tail
out=R/'tools/portrait_driver/audit_p36_visible.py'
assert not out.exists(),'Inspect existing audit script before replacing'
compile(audit,str(out),'exec');out.write_text(audit)
print('VISIBLE RUN: audit_p36_visible.py - read-only checks, no PCB regeneration',flush=True)
runpy.run_path(str(out),run_name='__main__')
