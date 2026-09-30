from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, shutil, subprocess

R=Path('/workspace/scratch/200245c5fbc3/chroma-badge')
E=R/'hardware/portrait/enclosure'; O=E/'output'; V=E/'validation'
B=R/'hardware/portrait/pcb/badge.kicad_pcb'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected='a6e52a432d860a8ce0d489fdaac9a9f9a56ae2c96e7ca05ce998e5b3b5a1cd40'
assert sha(B)==expected, 'Frozen PCB differs; stop before export'
pins=json.loads((R/'verification/visible-final/warning-review.json').read_text())['input_sha256']
pins['hardware/pcb/scripts/design.py']=sha(R/'hardware/pcb/scripts/design.py')
assert all(sha(R/p)==h for p,h in pins.items()), 'EDA freeze changed'
tag=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=V/('before-C1-'+tag); backup.mkdir()
for name in ('pcb_actual_export.step','pcb_board_body.step'):
    p=O/name
    if p.exists(): shutil.copy2(p,backup/name)
shutil.copy2(E/'snapshot_pcb.py',backup/'snapshot_pcb.py')
(V/'eda_frozen_inputs.json').write_text(json.dumps(pins,indent=2)+'\n')
cli='/workspace/scratch/200245c5fbc3/toolchain/bin/kicad-cli'
records=[]
def run(args, log):
    print('\nVISIBLE COMMAND:', ' '.join(args), flush=True)
    before={p:sha(R/p) for p in pins}
    with log.open('w') as f:
        proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in proc.stdout:
            print(line,end='',flush=True); f.write(line); f.flush()
        code=proc.wait()
    after={p:sha(R/p) for p in pins}
    records.append({'command':args,'exit_code':code,'input_before':before,'input_after':after,'log':str(log.relative_to(R))})
    assert before==after==pins, 'Export changed an EDA input'
    assert code==0, ('Export failed',log)

run([cli,'pcb','export','step','--force','--subst-models','--cut-vias-in-body','-o',str(O/'pcb_actual_export.step'),str(B)],V/'pcb_snapshot/step_export.log')
run([cli,'pcb','export','step','--force','--board-only','--cut-vias-in-body','-o',str(O/'pcb_board_body.step'),str(B)],V/'pcb_snapshot/board_step_export.log')
run([cli,'pcb','export','step','--force','--no-components','--include-tracks','--include-pads','--include-zones','--cut-vias-in-body','--no-extra-pad-thickness','-o',str(O/'pcb_copper_audit.step'),str(B)],V/'pcb_snapshot/copper_export.log')
(V/'pcb_snapshot/source_board.sha256').write_text(expected+'  hardware/portrait/pcb/badge.kicad_pcb\n')

p=E/'snapshot_pcb.py'; s=p.read_text()
def replace(old,new):
    global s
    assert s.count(old)==1, ('Snapshot anchor changed',old)
    s=s.replace(old,new)
replace('Run /usr/bin/python3.', 'Run only inside the KiCad 10 GUI Scripting Console.')
old=r"added=set(re.findall(r'Adding component (\S+)\.',log));missing=set(re.findall(r'Could not add 3D model to (\S+)\.',log))"
new=r'''step=(H/'output/pcb_actual_export.step').read_text()
labels=set(re.findall(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(\s*'[^']*'\s*,\s*'([^']+)'",step,re.S))
fprefs={fp.GetReference() for fp in b.GetFootprints()}
added=labels & fprefs
missing=set(re.findall(r'Could not add 3D model to (\S+)\.',log))-added
assert len(fprefs)==81 and re.search(r'\b10\.',pcbnew.GetBuildVersion()), 'Need final81 in KiCad10' '''
replace(old,new)
replace("elif '0805' in name:h=1.5;basis='Assumed0805 envelope; exact capacitor maxheight unverified'", "elif '0805' in name:h=1.6;basis='Selected TDK body max1.45 plus0.15 solder/engineering height allowance'")
replace("basis='Assumed1210 capacitor envelope; MPN/maxheight NOT locked'", "basis='Samsung CL32A107MQVNNNE body max2.8 plus0.2 engineering/solder budget'")
replace("parts.append({'ref':ref", "parts.append({'pcb_side':str(b.GetLayerName(fp.GetLayer())),'ref':ref")
replace("'board':str(PCB.relative_to(ROOT))", "'kicad_python_version':pcbnew.GetBuildVersion(),'model_export_evidence':'Reference assembly labels in actual STEP, not pre-load Adding component log; not a detailed-solid completeness claim','full_step_sha256':hashlib.sha256((H/'output/pcb_actual_export.step').read_bytes()).hexdigest(),'bare_step_sha256':hashlib.sha256((H/'output/pcb_board_body.step').read_bytes()).hexdigest(),'board':str(PCB.relative_to(ROOT))")
compile(s,str(p),'exec'); p.write_text(s)
assert all(sha(R/p)==h for p,h in pins.items())
outputs={str(p.relative_to(R)):sha(p) for p in (O/'pcb_actual_export.step',O/'pcb_board_body.step',O/'pcb_copper_audit.step',E/'snapshot_pcb.py')}
(V/'step_export_provenance.json').write_text(json.dumps({'status':'PASS_EXPORT_PROCESS_ONLY','stages':records,'outputs':outputs,'next':'Run snapshot_pcb.py in KiCad10 GUI; no geometry/physical acceptance yet'},indent=2)+'\n')
print('\nEXPORT STAGE COMPLETE. Frozen inputs unchanged. Next: visible KiCad10 snapshot and Physical Stackup review.',flush=True)
