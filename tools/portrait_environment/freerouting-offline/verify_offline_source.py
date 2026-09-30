#!/usr/bin/env python3
"""Static check only. Does not execute Freerouting or inspect a user board."""
from pathlib import Path
import hashlib,json,re,sys
base=Path(sys.argv[1]);local=Path(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
src=Path('src/main/java/app/freerouting')
allowed={'Freerouting.java','analytics/FRAnalytics.java','analytics/BigQueryClient.java','analytics/FreeroutingAnalyticsClient.java','analytics/SegmentClient.java','util/VersionChecker.java'}
changed=[]
for p in sorted((base/src).rglob('*.java')):
 rel=p.relative_to(base/src);q=local/src/rel
 if p.read_bytes()!=q.read_bytes():changed.append(str(rel))
assert set(changed)==allowed,changed
# Relevant application transport methods are removed, not just opted out via preferences.
for rel in ['analytics/FreeroutingAnalyticsClient.java','analytics/SegmentClient.java','analytics/BigQueryClient.java','util/VersionChecker.java']:
 text=(local/src/rel).read_text()
 for pattern in ['.openConnection(','.sendAsync(','.insertAll(','.refreshIfExpired(']:
  assert pattern not in text,(rel,pattern)
s=(local/src/'Freerouting.java').read_text()
assert 'new VersionChecker(' not in s
assert 'NetworkProxyConfig.configure(' not in s
for signature in ['public static Server initializeAPI(', 'public static Server initializeMCP(']:
 start=s.index(signature);opening=s.index('{',start);closing=s.index('}',opening)
 body=re.sub(r'//[^\n]*','',s[opening+1:closing]).strip();assert body=='return null;',body
for assignment in ['guiSettings.isEnabled = false','apiServerSettings.isEnabled = false','mcpServerSettings.isEnabled = false','mcpServerSettings.isStdioMode = false','usageAndDiagnosticData.disableAnalytics = true','userProfileSettings.isTelemetryAllowed = false']:
 assert s.index('globalSettings.'+assignment+';',s.index('globalSettings.applyCommandLineArguments(args);'))>0
assert 'analytics = null;' in (local/src/'analytics/FRAnalytics.java').read_text()
engine_dirs=['autoroute','board','geometry','core','rules','io','drc','management']
engine_files=[]
for folder in engine_dirs:
 for p in sorted((base/src/folder).rglob('*')):
  if p.is_file():
   rel=p.relative_to(base);assert p.read_bytes()==(local/rel).read_bytes(),rel;engine_files.append(str(rel))
r={'source_commit':'ae3d377740b6ffa744bed1bab26625fe0278fa90','static_review_passed':True,'modified_java_files':changed,'unchanged_engine_and_io_files':len(engine_files),'network_sink_removal_checked':True,'api_mcp_factories_return_null':True,'cli_env_cannot_reenable_telemetry_or_servers':True,'runtime_network_test_performed':False,'user_pcb_executed':False}
(out/'static-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
