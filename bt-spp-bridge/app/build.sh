#!/bin/sh
# ==============================================
# BUILD: BT SPP Bridge APK (Termux Native)
# Estratégia: aapt2+SDK33 (recursos) + javac+SDK36 (Java)
# ==============================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

APP_NAME="bt-spp-bridge"
BUILD_DIR="build"
APK_DIR="$BUILD_DIR/apk"

export JAVA_HOME="${JAVA_HOME:-$PREFIX/lib/jvm/java-21-openjdk}"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
ANDROID_JAR_33="$ANDROID_HOME/platforms/android-33/android-33-ext5/android.jar"
ANDROID_JAR_36="$ANDROID_HOME/platforms/android-36/android-36/android.jar"

cd "$PROJECT_DIR"

# Verify tools
for tool in javac aapt2 dx apksigner; do
    if ! command -v $tool >/dev/null 2>&1; then
        echo "❌ $tool não encontrado. Instale: pkg install openjdk-21 aapt2 dx apksigner"
        exit 1
    fi
done

for jar in "$ANDROID_JAR_33" "$ANDROID_JAR_36"; do
    if [ ! -f "$jar" ]; then
        echo "❌ android.jar não encontrado: $jar"
        exit 1
    fi
done

echo "🔨 Buildando $APP_NAME..."
echo "   JAVA_HOME=$JAVA_HOME"
echo "   SDK 33: $ANDROID_JAR_33"
echo "   SDK 36: $ANDROID_JAR_36"
echo ""

# Clean
rm -rf "$BUILD_DIR"
mkdir -p "$APK_DIR" "$BUILD_DIR/classes" "$BUILD_DIR/R"

# -----------------------------------------------
# STEP 1: Create resources if missing
# -----------------------------------------------
if [ ! -f app/src/main/res/values/strings.xml ]; then
    mkdir -p app/src/main/res/values
    echo '<?xml version="1.0" encoding="utf-8"?><resources><string name="app_name">BT SPP Bridge</string></resources>' > app/src/main/res/values/strings.xml
fi

# -----------------------------------------------
# STEP 2: aapt2 compile + link (platform-33 — INJETA versionCode!)
# -----------------------------------------------
echo "📦 [2/6] aapt2 compile..."
aapt2 compile --dir app/src/main/res -o "$BUILD_DIR/compiled.flata"

echo "📦 [3/6] aapt2 link (platform-33)..."
aapt2 link \
    -o "$APK_DIR/base.apk" \
    -I "$ANDROID_JAR_33" \
    --manifest app/src/main/AndroidManifest.xml \
    --java "$BUILD_DIR/R" \
    --min-sdk-version 26 \
    --target-sdk-version 33 \
    --version-code 1 \
    --version-name "1.0" \
    "$BUILD_DIR/compiled.flata"

# -----------------------------------------------
# STEP 3: Compile Java (platform-36 — API completa)
# -----------------------------------------------
echo "☕ [4/6] Compilando Java..."
JAVA_SRC=$(find app/src/main/java -name "*.java" 2>/dev/null)

javac \
    --release 8 \
    -cp "$ANDROID_JAR_36" \
    -d "$BUILD_DIR/classes" \
    $JAVA_SRC \
    $(find "$BUILD_DIR/R" -name "*.java" 2>/dev/null)

# -----------------------------------------------
# STEP 4: Convert to DEX (dx)
# -----------------------------------------------
echo "📱 [5/6] dx..."
dx --dex --output="$BUILD_DIR/classes.dex" "$BUILD_DIR/classes"

cp "$BUILD_DIR/classes.dex" "$APK_DIR/"
cd "$APK_DIR" && aapt add base.apk classes.dex 2>/dev/null; cd "$PROJECT_DIR"

# -----------------------------------------------
# STEP 5: Sign APK
# -----------------------------------------------
echo "✍️  [6/6] apksigner..."
DEBUG_KEYSTORE="$HOME/.android/debug.keystore"
DEBUG_ALIAS="androiddebugkey"
DEBUG_PASS="android"

if [ ! -f "$DEBUG_KEYSTORE" ]; then
    mkdir -p "$HOME/.android"
    keytool -genkey -v \
        -keystore "$DEBUG_KEYSTORE" \
        -alias "$DEBUG_ALIAS" \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass "$DEBUG_PASS" -keypass "$DEBUG_PASS" \
        -dname "CN=Debug, OU=Termux, O=BTBridge, L=Unknown, ST=Unknown, C=BR"
fi

apksigner sign \
    --ks "$HOME/.android/debug.keystore" \
    --ks-pass pass:"$DEBUG_PASS" \
    --ks-key-alias "$DEBUG_ALIAS" \
    --out "$PROJECT_DIR/$BUILD_DIR/$APP_NAME.apk" \
    "$PROJECT_DIR/$APK_DIR/base.apk"

echo ""
echo "============================================="
echo "✅ BUILD SUCESSO!"
echo "   APK: $BUILD_DIR/$APP_NAME.apk"
echo "   $(du -h $BUILD_DIR/$APP_NAME.apk | cut -f1)"
echo "============================================="
echo ""
echo "📲 Instalar: termux-open $BUILD_DIR/$APP_NAME.apk"
echo "📡 Usar: nc localhost 8090"
