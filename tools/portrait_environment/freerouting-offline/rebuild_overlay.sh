#!/usr/bin/env bash
# Offline compilation only; deliberately never launches Freerouting.
set -euo pipefail
BASE=/workspace/scratch/200245c5fbc3
TOOLS="$BASE/chroma-badge/tools/portrait_environment/freerouting-offline"
SOURCE="$BASE/toolchain/freerouting-offline-source"
OFFICIAL="$BASE/toolchain/freerouting-2.4.1.jar"
JDK="$BASE/toolchain/jdk-25.0.4.1+1"
DEST="${1:?Pass a NEW candidate JAR path; existing artifacts are never overwritten}"
[[ ! -e "$DEST" ]] || { echo "Refusing to overwrite $DEST" >&2; exit 2; }
CLASSES="$(mktemp -d "$BASE/toolchain/offline-classes-XXXXXXXX")"
python3 "$TOOLS/verify_offline_source.py" "$BASE/freerouting-source" "$SOURCE" "$TOOLS"
cd "$SOURCE"
"$JDK/bin/javac" -encoding UTF-8 --release 25 -classpath "$OFFICIAL" -d "$CLASSES" \
  src/main/java/app/freerouting/Freerouting.java \
  src/main/java/app/freerouting/analytics/{FRAnalytics,FreeroutingAnalyticsClient,SegmentClient,BigQueryClient}.java \
  src/main/java/app/freerouting/util/VersionChecker.java
python3 "$TOOLS/package_overlay.py" "$OFFICIAL" "$CLASSES" "$SOURCE/LOCAL_ONLY_NOTICE.md" "$TOOLS/local-only.patch" "$DEST" "${DEST}.manifest.json"
# Inspect bytecode; no target program execution.
"$JDK/bin/javap" -classpath "$DEST" -p -c app.freerouting.Freerouting app.freerouting.util.VersionChecker \
 app.freerouting.analytics.FRAnalytics app.freerouting.analytics.FreeroutingAnalyticsClient \
 app.freerouting.analytics.SegmentClient app.freerouting.analytics.BigQueryClient > "${DEST}.bytecode.txt"
echo "Candidate built for review; not executed. Package ZIP timestamps may change its hash across rebuilds."
