#!/usr/bin/env python3
"""Package compiled no-network classes over a hash-pinned official fat JAR.
This is not an official Gradle build. Never executes the resulting artifact.
"""
from pathlib import Path
import hashlib,json,zipfile,sys,textwrap
base=Path(sys.argv[1]);classes=Path(sys.argv[2]);notice=Path(sys.argv[3]);patch=Path(sys.argv[4]);output=Path(sys.argv[5]);evidence=Path(sys.argv[6])
expected='251101c3eeac22d7e7dfcf6796603279e5d1000283eb82d8f093780f7afc6aa9'
assert hashlib.sha256(base.read_bytes()).hexdigest()==expected,'Unrecognized base JAR'
compiled={str(p.relative_to(classes)):p for p in classes.rglob('*.class')}
tops=['app/freerouting/Freerouting','app/freerouting/analytics/FRAnalytics','app/freerouting/analytics/FreeroutingAnalyticsClient','app/freerouting/analytics/SegmentClient','app/freerouting/analytics/BigQueryClient','app/freerouting/util/VersionChecker']
assert set(compiled)=={s+'.class' for s in tops},compiled.keys()
def replaced(name):return any(name==s+'.class' or (name.startswith(s+'$') and name.endswith('.class')) for s in tops)
patch_sha=hashlib.sha256(patch.read_bytes()).hexdigest();unchanged=0;removed=[]
with zipfile.ZipFile(base) as zin, zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as zout:
 for info in zin.infolist():
  if replaced(info.filename):removed.append(info.filename);continue
  data=zin.read(info)
  if info.filename=='META-INF/MANIFEST.MF':
   fields=[]
   for line in data.decode().replace('\r\n','\n').splitlines():
    if line.startswith(' ') and fields:fields[-1]+=line[1:]
    elif line:fields.append(line)
   fields=[x for x in fields if not x.startswith(('Build-Revision:','Implementation-Version:'))]
   fields+=['Build-Revision: ae3d377740b6ffa744bed1bab26625fe0278fa90-local-only1','Implementation-Version: 2.4.1-local-only1','Local-Only: true','Offline-Patch-SHA256: '+patch_sha]
   folded=[]
   for line in fields:
    folded.append(line[:70]);line=line[70:]
    while line:folded.append(' '+line[:69]);line=line[69:]
   data=('\r\n'.join(folded)+'\r\n\r\n').encode()
  else:unchanged+=1
  zout.writestr(info,data)
 for name,path in compiled.items():zout.writestr(name,path.read_bytes())
 zout.writestr('LOCAL_ONLY_NOTICE.md',notice.read_bytes())
with zipfile.ZipFile(base) as a,zipfile.ZipFile(output) as b:
 for name in a.namelist():
  if name!='META-INF/MANIFEST.MF' and not replaced(name):assert a.read(name)==b.read(name),name
 for name,p in compiled.items():assert b.read(name)==p.read_bytes(),name
r={'build_method':'javac25 overlay on pinned official fat JAR, not a successful Gradle build','base_sha256':expected,'patch_sha256':patch_sha,'candidate_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'candidate_path':str(output),'overlaid_classes':sorted(compiled),'removed_original_classes':removed,'unmodified_archive_entries':unchanged,'candidate_executed':False,'user_pcb_executed':False}
evidence.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
