"""Compare the netlist exported from the generated schematic against design.py."""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import design as D
HERE = os.path.dirname(__file__)
t = open(os.path.join(HERE, "..", "output", "badge.net")).read()
sch = {}
# KiCad 9: (net (code "1") (name "GND") ... on one line
# KiCad 10: (net\n  (code "1")\n  (name "+3V3")\n  (node\n    (ref "C4") ...
net_re = re.compile(
    r'\(\s*net\s*\(\s*code\s+"\d+"\s*\)\s*\(\s*name\s+"([^"]+)"\s*\)(.*?)(?=\(\s*net\s*\(\s*code|\Z)',
    re.S,
)
for m in net_re.finditer(t):
    name, body = m.group(1), m.group(2)
    sch[name.lstrip('/')] = set(re.findall(r'\(\s*ref\s+"([^"]+)"\s*\)\s*\(\s*pin\s+"([^"]+)"\s*\)', body))
des = {n: set(p) for n, p in D.all_nets().items()}
bad = 0
for n, p in des.items():
    if n not in sch:
        print('missing net', n); bad += 1; continue
    if sch[n] != p:
        print('diff', n, sch[n] ^ p); bad += 1
extra = [e for e in set(sch) - set(des) if not e.startswith('unconnected')]
if extra:
    print('extra nets in schematic:', extra); bad += 1
print('netlist matches design.py' if not bad else f'{bad} problems', '|', len(sch), 'schematic nets')
sys.exit(1 if bad else 0)
