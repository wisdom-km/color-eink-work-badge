"""Visible stage runner: records before hashes BEFORE launching, retains failures."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,subprocess,sys
H=Path(__file__).resolve().parent; R=H.parents[2]; V=H/'validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
name=sys.argv[1]; command=sys.argv[2:]; assert command
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
folder=V/'executions'; folder.mkdir(exist_ok=True)
pins=json.loads((V/'eda_frozen_inputs.json').read_text())
assert all(sha(R/p)==h for p,h in pins.items()), 'EDA freeze changed'
paths=set(H.glob('*.py'))|set(H.glob('*.FCMacro'))|{R/p for p in pins}
paths|={p for p in (R/'hardware/portrait/pcb/lib').rglob('*') if p.is_file() and p.suffix.lower() in ('.step','.stp','.kicad_mod')}
paths|={p for p in (H/'sources').glob('*') if p.is_file()}
paths|={V/'pcb_model_coverage.json',V/'stackup_gui_observed.txt'}
before={str(p.relative_to(R)):sha(p) for p in sorted(paths)}
record={'stage':name,'started_utc':stamp,'command':command,'input_before':before}
path=folder/(stamp+'-'+name+'.json')
path.write_text(json.dumps(record,indent=2)+'\n')
print('VISIBLE STAGE',name,'COMMAND',command,flush=True)
with (folder/(stamp+'-'+name+'.log')).open('w') as log:
    proc=subprocess.Popen(command,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    for line in proc.stdout:
        print(line,end='',flush=True); log.write(line); log.flush()
    code=proc.wait()
after={str(p.relative_to(R)):sha(p) for p in sorted(paths)}
record.update(exit_code=code,input_after=after,source_unchanged=before==after,finished_utc=datetime.now(timezone.utc).isoformat())
record['outputs']={str(p.relative_to(R)):sha(p) for p in sorted(list((H/'output').glob('*'))+list(V.glob('*.json'))) if p.is_file()}
path.write_text(json.dumps(record,indent=2)+'\n')
assert all(sha(R/p)==h for p,h in pins.items()), 'Stage modified frozen EDA inputs'
assert before==after, 'Source changed during stage'
print('STAGE_EXIT',code,'EVIDENCE',path,flush=True)
sys.exit(code)
