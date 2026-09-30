#!/usr/bin/env python3
"""Build an independent command/data oracle from pinned official vendor source."""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--vendor',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
expected_sha = "5a6b79434963dade51244d4ec7cb16fc6cc35b31703073b32b186792ac58fcca"
if hashlib.sha256(a.vendor.read_bytes()).hexdigest() != expected_sha:
    raise SystemExit("Official source hash mismatch; review before replacing the golden oracle")
s=a.vendor.read_text()
def body(name):
    m=re.search(r'\b'+re.escape(name)+r'\(void\)\s*\{',s)
    if not m: raise ValueError(name)
    pos=m.end();depth=1;end=pos
    while depth:
        if s[end]=='{':depth+=1
        if s[end]=='}':depth-=1
        end+=1
    return s[pos:end-1]
def events(name):
    return [(k=='Data',int(v,16)) for k,v in re.findall(r'EPD_3IN6E_Send(Command|Data)\((0[xX][0-9a-fA-F]+)\)',body(name))]
rows={k:events(v) for k,v in [('init','EPD_3IN6E_Init'),('turn_on','EPD_3IN6E_TurnOnDisplay'),('sleep','EPD_3IN6E_Sleep')]}
a.out.mkdir(parents=True,exist_ok=True)
for k,v in rows.items(): assert v,k
header='// Generated from pinned official source, not the implementation under test.\n#pragma once\n'
for k,v in rows.items():
    header+='const std::vector<Event> oracle_'+k+' = {'+','.join('{'+str(int(d))+',0x'+f'{b:02X}'+'}' for d,b in v)+'};\n'
(a.out/'vendor_oracle.h').write_text(header)
(a.out/'vendor-oracle.json').write_text(json.dumps({'source':str(a.vendor),'sha256':hashlib.sha256(a.vendor.read_bytes()).hexdigest(),'events':rows},indent=2)+'\n')
print({k:len(v) for k,v in rows.items()})
