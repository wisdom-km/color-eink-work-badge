#!/usr/bin/env python3
"""Apply reviewable local-only modifications to a COPY of pinned official source.
Never launches Freerouting and never reads any user PCB file.
"""
from pathlib import Path
import sys
root=Path(sys.argv[1]);src=root/'src/main/java/app/freerouting'
def replace_method(rel, signature, replacement):
    p=src/rel;s=p.read_text();start=s.index(signature);op=s.index('{',start);n=1;i=op+1
    while n:
        n+=(s[i]=='{')-(s[i]=='}');i+=1
    s=s[:op+1]+'\n'+replacement+'\n  '+s[i-1:];p.write_text(s)
replace_method(Path('analytics/FRAnalytics.java'),'public static void setAccessKey(',
    '    // LOCAL-ONLY BUILD: never construct an analytics transport.\n    analytics = null;')
for file in ('analytics/FreeroutingAnalyticsClient.java','analytics/SegmentClient.java'):
    replace_method(Path(file),'private void sendPayloadAsync(',
        '    // LOCAL-ONLY BUILD: deliberate no-op, no executor, socket or payload transmission.')
replace_method(Path('analytics/BigQueryClient.java'),'private static BigQuery createBigQueryService(',
    '    // LOCAL-ONLY BUILD: no credentials parsing, token refresh or BigQuery service.\n    return null;')
replace_method(Path('analytics/BigQueryClient.java'),'private void sendPayloadAsync(',
    '    // LOCAL-ONLY BUILD: deliberate no-op; no BigQuery insertion.')
replace_method(Path('util/VersionChecker.java'),'private static HttpClient createDefaultHttpClient(',
    '    // LOCAL-ONLY BUILD: do not even construct an HTTP client.\n    return null;')
replace_method(Path('util/VersionChecker.java'),'public void run()',
    '    // LOCAL-ONLY BUILD: release lookup is disabled, including help invocations.')
p=src/'Freerouting.java';s=p.read_text()
s=s.replace('    globalSettings.applyCommandLineArguments(args);','''    globalSettings.applyCommandLineArguments(args);

    // LOCAL-ONLY BUILD: immutable execution policy, overriding CLI/env/config.
    // No server, GUI/browser callback, or telemetry can be re-enabled by options.
    globalSettings.guiSettings.isEnabled = false;
    globalSettings.apiServerSettings.isEnabled = false;
    globalSettings.mcpServerSettings.isEnabled = false;
    globalSettings.mcpServerSettings.isStdioMode = false;
    globalSettings.usageAndDiagnosticData.disableAnalytics = true;
    globalSettings.userProfileSettings.isTelemetryAllowed = false;''')
s=s.replace('    NetworkProxyConfig.configure(globalSettings.networkSettings);',
    '    // LOCAL-ONLY BUILD: no proxy/truststore initialization is needed.')
old='''    VersionChecker checker = new VersionChecker(Constants.FREEROUTING_VERSION);
    Thread versionThread = new Thread(checker, "version-checker");
    versionThread.setDaemon(true);
    versionThread.start();'''
assert old in s;s=s.replace(old,'    // LOCAL-ONLY BUILD: version-checker thread intentionally not created.')
s=s.replace('FRLogger.info("Freerouting " + VERSION_NUMBER_STRING);',
    'FRLogger.info("Freerouting " + VERSION_NUMBER_STRING + " [LOCAL-ONLY PATCHED BUILD]");')
p.write_text(s)
# Defense in depth: network server factories cannot be invoked even accidentally.
# Keep signatures for build/source compatibility while eliminating listener setup.
for name in ('initializeAPI','initializeMCP'):
    replace_method(Path('Freerouting.java'),'public static Server '+name+'(',
        '    // LOCAL-ONLY BUILD: REST/MCP servers and their outbound adapters are unavailable.\n    return null;')
print('Local-only patch applied. Router algorithms and board IO unchanged.')
