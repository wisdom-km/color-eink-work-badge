from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil
E=Path(__file__).resolve().parent; R=E.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pins=json.loads((E/'validation/eda_frozen_inputs.json').read_text())
assert all(sha(R/p)==h for p,h in pins.items())
for name in ('c1_config.py','c1_geometry.py'):
    p=E/name; compile(p.read_text(),str(p),'exec')
p=E/'build_enclosure.py'; s=p.read_text()
old='C = design.PORTRAIT'
new='from c1_config import configure\nC = configure(design.PORTRAIT)'
if new not in s:
    assert s.count(old)==1; s=s.replace(old,new)
anchor="if __name__=='__main__':main()"
hook="from c1_geometry import install as install_c1\ninstall_c1(sys.modules[__name__])\n\n"+anchor
if hook not in s:
    assert s.count(anchor)==1; s=s.replace(anchor,hook)
compile(s,str(p),'exec')
backup=E/'validation'/('build_before_C1_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.py')
shutil.copy2(p,backup); p.write_text(s)
assert all(sha(R/p)==h for p,h in pins.items())
print('C1 activated in mechanical build only. Frozen electrical inputs unchanged. Now run build_enclosure.py visibly.')
