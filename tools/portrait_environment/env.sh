# Source this from any directory. All application state stays in writable workspace.
export BADGE_TOOLCHAIN_ROOT=/workspace/scratch/200245c5fbc3/toolchain
export HOME="$BADGE_TOOLCHAIN_ROOT/home"
export XDG_CACHE_HOME="$BADGE_TOOLCHAIN_ROOT/cache"
export XDG_CONFIG_HOME="$BADGE_TOOLCHAIN_ROOT/config"
export XDG_DATA_HOME="$BADGE_TOOLCHAIN_ROOT/data"
export XDG_STATE_HOME="$BADGE_TOOLCHAIN_ROOT/state"
export PLATFORMIO_CORE_DIR="$BADGE_TOOLCHAIN_ROOT/platformio-core"
export PLATFORMIO_BUILD_DIR="$BADGE_TOOLCHAIN_ROOT/platformio-build"
export PATH="$BADGE_TOOLCHAIN_ROOT/bin:$BADGE_TOOLCHAIN_ROOT/platformio-venv/bin:$PATH"
export PLATFORMIO_SETTING_ENABLE_TELEMETRY=No
export KICAD10_SYMBOL_DIR="$BADGE_TOOLCHAIN_ROOT/squashfs-root/share/kicad/symbols"
export KICAD10_FOOTPRINT_DIR="$BADGE_TOOLCHAIN_ROOT/squashfs-root/share/kicad/footprints"
export JAVA_HOME="$BADGE_TOOLCHAIN_ROOT/jdk-25.0.4.1+1-jre"
export PATH="$JAVA_HOME/bin:$PATH"
export PLATFORMIO_LIBDEPS_DIR="$BADGE_TOOLCHAIN_ROOT/platformio-libdeps"
