# 🏗️ Build de APK Android Nativo no Termux — Guia Completo

> Como compilar um APK inteiro dentro do Termux, sem PC, sem root, sem Android Studio.
> Projeto de referência: BT SPP Bridge (Bluetooth → TCP)
> Dispositivo: Samsung Galaxy S23 (Android 14, SDK 36, ARM64)

---

## 📦 Estrutura do Projeto

```
~/projetos/bt-spp-bridge/
├── README.md              ← este arquivo
├── TERMUX_API_GUIA.md     ← referência completa da API do Termux
├── esp32_bt_temp.ino      ← código ESP32 Bluetooth SPP
├── app/                   ← código fonte do APK
│   ├── build.sh           ← script de build (1 comando)
│   ├── PLANO.md           ← 20 erros com causa/solução (histórico vivo)
│   ├── SUCESSO.md         ← documentação completa do projeto
│   ├── DEBUG_RELATORIO.md ← análise de debug da comunicação
│   ├── GUIA_T470.md       ← guia do servidor SPP no notebook
│   ├── INVESTIGACAO_T470.md ← checkpoints de debug
│   ├── REVIEW.json        ← análise estruturada de erros
│   ├── build/             ← APK buildado
│   └── app/src/main/      ← código fonte
│       ├── AndroidManifest.xml
│       ├── res/values/strings.xml
│       └── java/com/termux/bridge/
│           ├── MainActivity.java      ← UI (lista pareados + scan)
│           └── BridgeService.java     ← serviço foreground (BT ↔ TCP)
└── bt_spp_java_helper/    ← helper Java (não usado no build final)
```

---

## 🧰 Pré-requisitos (instalar 1 vez)

```bash
# Ferramentas de build
pkg install openjdk-21 aapt2 dx apksigner curl -y

# Ferramentas de rede (para testar)
pkg install netcat-openbsd -y
```

---

## 📥 Download dos SDKs Android (1 vez)

O Termux NÃO tem Android SDK nos repositórios. É preciso baixar manualmente.

```bash
mkdir -p ~/android-sdk/platforms

# SDK 33 — para aapt2 (recursos, compatível com aapt2 v2.19 do Termux)
curl -L -o /tmp/platform-33.zip \
  "https://dl.google.com/android/repository/platform-33-ext5_r01.zip"
unzip -q /tmp/platform-33.zip -d ~/android-sdk/platforms/android-33/

# SDK 36 — para javac (API mais completa)
curl -L -o /tmp/platform-36.zip \
  "https://dl.google.com/android/repository/platform-36_r01.zip"
unzip -q /tmp/platform-36.zip -d ~/android-sdk/platforms/android-36/
```

**Por que 2 SDKs?**
- `aapt2` v2.19 (Termux) só carrega `platform-33/android.jar`
- `platform-36` falha com `failed to load include path`
- `javac` pode usar `platform-36` para compilar contra API mais recente

---

## 🔨 Build (1 comando)

```bash
cd ~/projetos/bt-spp-bridge/app
bash build.sh
```

### O que o build.sh faz:

```
┌─────────────────────────────────────────────┐
│ STEP 1: Criar resources (strings.xml)        │
├─────────────────────────────────────────────┤
│ STEP 2: aapt2 compile                       │
│   Entrada:  res/values/strings.xml           │
│   Saída:    build/compiled.flata             │
├─────────────────────────────────────────────┤
│ STEP 3: aapt2 link                          │
│   Entrada:  compiled.flata + AndroidManifest │
│   Saída:    build/apk/base.apk + R.java      │
│   SDK:      platform-33 (compatível aapt2)   │
│   Flags:    --min-sdk-version 26             │
│             --target-sdk-version 33          │
│             --version-code 1                 │
│             --version-name "1.0"             │
├─────────────────────────────────────────────┤
│ STEP 4: javac                              │
│   Entrada:  MainActivity.java +              │
│             BridgeService.java + R.java      │
│   Saída:    build/classes/*.class            │
│   SDK:      platform-36 (API completa)       │
│   Flags:    --release 8                      │
├─────────────────────────────────────────────┤
│ STEP 5: dx (DEX)                           │
│   Entrada:  build/classes/                   │
│   Saída:    build/classes.dex                │
│   ⚠️ Usa dx (NÃO d8 — bugado no Termux)     │
├─────────────────────────────────────────────┤
│ STEP 6: aapt add + apksigner               │
│   Adiciona classes.dex ao base.apk          │
│   Assina com debug.keystore                 │
│   Saída:    build/bt-spp-bridge.apk          │
└─────────────────────────────────────────────┘
```

---

## 📋 Regras de Ouro (15 regras)

| # | Regra | Se violar... |
|---|-------|-------------|
| 1 | **aapt2 + platform-33** | aapt2 não carrega o android.jar |
| 2 | **javac + platform-36** | Pode usar 33 também, mas 36 = API completa |
| 3 | **dx** (nunca d8) | d8 crasha NullPointerException em inner classes |
| 4 | **javac --release 8** | Java 21 não aceita source < 8 |
| 5 | **NUNCA usar lambdas (`->`)** | Erro: LambdaMetafactory não existe no Android SDK |
| 6 | **minSdkVersion >= 26** | Android 14 bloqueia instalação de apps antigos |
| 7 | **android:exported** na Activity | "problem parsing the package" |
| 8 | **android:foregroundServiceType** | Crash no startForeground() |
| 9 | **BLUETOOTH_CONNECT em runtime** | SecurityException ao criar socket |
| 10 | **ACCESS_FINE_LOCATION** no scan | Scan retorna 0 dispositivos |
| 11 | **Tema Material no AndroidManifest** | Crash ao iniciar Activity |
| 12 | **FOREGROUND_SERVICE_CONNECTED_DEVICE** | Crash ao iniciar serviço |
| 13 | **Paths absolutos** no script | apksigner "file not found" |
| 14 | **SDK completo** (não framework.jar) | aapt não encontra attrs.xml |
| 15 | **cp classes.dex pro APK_DIR** | DEX não incluído no APK |

---

## 🐛 Erros Comuns e Soluções

### `attribute android:name not found`
→ aapt2 com platform errada. **Use platform-33.**

### `failed to load include path`
→ platform-34/35/36 incompatível com aapt2 v2.19. **Use platform-33.**

### `Source option 7 is no longer supported`
→ **Use `--release 8`**

### `cannot find symbol: method metafactory`
→ Você usou lambda (`->`). **Substitua por classe anônima.**

### `NullPointerException in d8/R8`
→ d8 quebrado no Termux ARM64. **Use `dx`.**

### `problem parsing the package`
→ Falta `android:exported` na Activity. **Adicione.**

### `App not compatible with your phone`
→ minSdkVersion muito baixo. **Use >= 26.**

### Scan não retorna nada
→ Falta `ACCESS_FINE_LOCATION` em runtime. **Adicione no requestPermissions.**

### Crash ao conectar Bluetooth
→ `BLUETOOTH_CONNECT` não foi solicitado em runtime. **Adicione.**

---

## 📱 Instalação

```bash
# Copiar pro armazenamento
cp ~/projetos/bt-spp-bridge/app/build/bt-spp-bridge.apk /storage/emulated/0/

# No gerenciador de arquivos do celular, tocar no APK
```

---

## 🚀 Uso

### Com ESP32:
1. Programar ESP32 com `esp32_bt_temp.ino`
2. Parear via Bluetooth do Android
3. Abrir BT SPP Bridge → tocar no ESP32
4. `nc localhost 8090`

### Com notebook Linux:
1. Rodar servidor SPP no notebook (ver `GUIA_T470.md`)
2. Parear via Bluetooth do Android
3. Abrir BT SPP Bridge → escanear → tocar no notebook
4. `nc localhost 8090`

---

## 📊 APK Final

| Atributo | Valor |
|----------|-------|
| package | `com.termux.bridge` |
| versionCode | 1 |
| versionName | 1.0 |
| minSdkVersion | 26 |
| targetSdkVersion | 33 |
| tamanho | ~20 KB |
| permissões | INTERNET, BLUETOOTH×4, LOCATION×2, FOREGROUND_SERVICE×2, POST_NOTIFICATIONS |

---

## 🔗 Referências

- [PLANO.md](app/PLANO.md) — 20 erros documentados com timeline
- [SUCESSO.md](app/SUCESSO.md) — Documentação completa do projeto
- [DEBUG_RELATORIO.md](app/DEBUG_RELATORIO.md) — Análise de debug sem suposições
- [GUIA_T470.md](app/GUIA_T470.md) — Servidor SPP no Linux
- [INVESTIGACAO_T470.md](app/INVESTIGACAO_T470.md) — Checkpoints de debug T470
- [TERMUX_API_GUIA.md](TERMUX_API_GUIA.md) — Guia completo Termux:API
