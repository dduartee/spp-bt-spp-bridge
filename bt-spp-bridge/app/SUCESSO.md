# 🏁 Desenvolvimento Android Nativo no Termux — Samsung S23

> Build completo de APK no Termux ARM64, sem PC, sem root, sem Android Studio.
> Projeto: BT SPP Bridge (Bluetooth → TCP para Termux + ESP32)
> Data: 2026-06-10 | Dispositivo: Samsung Galaxy S23 (Android 14, SDK 36)

---

## 🎯 Visão Geral

Criar um APK que faz ponte entre Bluetooth SPP do ESP32 e uma porta TCP local,
permitindo que o Termux se comunique com o ESP32 via `nc localhost 8090`.

**Tudo feito nativamente no Termux do S23 — sem PC.**

---

## 📦 Stack de Ferramentas (Termux)

| Ferramenta | Pacote | Versão | Função |
|-----------|--------|--------|--------|
| `aapt2` | aapt2 | 2.19 | Compilar recursos XML → binário |
| `javac` | openjdk-21 | 21.0.11 | Compilar Java → .class |
| `dx` | dx | 1.16 | Converter .class → classes.dex |
| `apksigner` | apksigner | 33.0.1 | Assinar APK |
| `curl` | curl | — | Baixar SDK platforms |
| `keytool` | openjdk-21 | 21 | Gerar keystore debug |

### Plataformas SDK baixadas:
| SDK | Uso | Tamanho |
|-----|-----|---------|
| platform-33 (ext5) | aapt2 recursos | ~80 MB |
| platform-36 | javac compilação | ~200 MB |

---

## 🧱 Arquitetura do APK

```
bt_bridge_app/
├── build.sh                          # Script de build (1 comando)
├── PLANO.md                          # Histórico de erros e decisões
├── SUCESSO.md                        # Este documento
├── REVIEW.json                       # Análise de erros em JSON
├── app/src/main/
│   ├── AndroidManifest.xml
│   │   ├── Permissões: INTERNET, BLUETOOTH, BLUETOOTH_ADMIN,
│   │   │              BLUETOOTH_CONNECT, BLUETOOTH_SCAN,
│   │   │              FOREGROUND_SERVICE, FOREGROUND_SERVICE_CONNECTED_DEVICE,
│   │   │              POST_NOTIFICATIONS
│   │   ├── Activity: MainActivity (exported=true, lista pareados)
│   │   └── Service:  BridgeService (foreground, connectedDevice)
│   ├── res/values/strings.xml
│   └── java/com/termux/bridge/
│       ├── MainActivity.java         # UI programática, permissão runtime
│       └── BridgeService.java        # BT SPP ↔ TCP bridge
└── build/
    └── bt-spp-bridge.apk             # APK final (~20 KB)
```

---

## 🔄 Fluxo do App

```
1. MainActivity.onCreate()
   ├── requestPermissions(BLUETOOTH_CONNECT)  // Android 12+
   ├── BluetoothAdapter.getDefaultAdapter()
   └── loadPairedDevices()
       └── Para cada device pareado: botão com nome + MAC

2. Usuário toca no ESP32
   ├── connectToDevice()
   ├── Verifica BLUETOOTH_CONNECT (runtime)
   ├── startForegroundService(BridgeService)
   └── statusText: "🔗 Conectado"

3. BridgeService.onStartCommand()
   ├── createRfcommSocketToServiceRecord(SPP_UUID)
   ├── btSocket.connect()
   ├── startTcpBridge() → ServerSocket(8090)
   └── Loop: BT InputStream → sendToTcp()

4. No Termux: nc localhost 8090
   ├── TCP → TcpReader → btSocket.getOutputStream()
   └── btSocket.getInputStream() → sendToTcp() → TCP
```

---

## 🧪 Cronologia Completa de Erros

### Fase 1: Compilação de Recursos (aapt2)

| # | Erro | Causa | Solução |
|---|------|-------|---------|
| 1 | `attribute android:name not found` | aapt2 v2.19 incompatível com platform-36 | **Usar platform-33** |
| 2 | `failed to load include path` | android.jar SDK 36 não carrega no aapt2 | Baixar `platform-33-ext5_r01.zip` |
| 3 | `No resource identifier for 'maxSdkVersion'` | `/system/framework/framework.jar` é DEX, não SDK | **Baixar SDK completo**, NUNCA usar framework.jar |

**Insight:** O aapt2 do Termux (v2.19) é compatível APENAS com platform-33. Versões mais novas (34, 35, 36) falham com "failed to load include path". Isso é uma limitação conhecida do build ARM64.

### Fase 2: Compilação Java

| # | Erro | Causa | Solução |
|---|------|-------|---------|
| 4 | `Source option 7 no longer supported` | Java 21 mínimo é 8 | `javac --release 8` |
| 5 | `cannot find symbol: metafactory` | Lambda (`->`) precisa de LambdaMetafactory inexistente no Android SDK | **NUNCA usar lambdas** no código |
| 6 | `cannot find symbol: metafactory` (de novo) | Lambdas em listeners de botão | Implementar `View.OnClickListener` na Activity + `HashMap<View, Device>` |
| 7 | `cannot find symbol: metafactory` (BridgeService) | Lambdas em Threads | Usar **named inner classes** em vez de anônimas |

**Insight:** O Android SDK NÃO inclui LambdaMetafactory. Todo código Java para Android buildado com javac direto deve usar classes anônimas tradicionais ou named inner classes. Isso é uma diferença fundamental entre build Gradle (Android Studio) e build manual.

### Fase 3: DEX

| # | Erro | Causa | Solução |
|---|------|-------|---------|
| 8 | `NullPointerException: Cannot invoke String.length()` | **BUG no d8/R8** 3.3.20-dev (Termux ARM64) — crasha em QUALQUER classe interna | **Usar `dx`** em vez de `d8` |
| 9 | `class name does not match path` | dx precisa do diretório raiz, não arquivos individuais | `dx --dex --output=out.dex build/classes/` |

**Insight:** O d8 do Termux é fundamentalmente quebrado para classes com inner classes (anônimas OU nomeadas). O erro `NullPointerException: Cannot invoke "String.length()"` ocorre no construtor `d1.<init>` do R8 e afeta 100% dos .class com `$` no nome. `dx` (legado) funciona perfeitamente.

### Fase 4: Empacotamento e Assinatura

| # | Erro | Causa | Solução |
|---|------|-------|---------|
| 10 | `FileNotFoundException: build/apk/base.apk` | `PROJECT_DIR` relativo quebra com `cd` durante build | `$(cd "$(dirname "$0")" && pwd)` |
| 11 | `aapt add` não encontra classes.dex | classes.dex em BUILD_DIR, add roda em APK_DIR | `cp $BUILD_DIR/classes.dex $APK_DIR/` antes do add |

### Fase 5: Instalação

| # | Erro | Causa | Solução |
|---|------|-------|---------|
| 12 | `"problem parsing the package"` (v1) | aapt v1 não injeta versionCode/versionName | **Usar aapt2** com `--version-code` |
| 13 | `"problem parsing the package"` (v2) | `android:exported` ausente na Activity | Adicionar `android:exported="true"` |
| 14 | `"App not compatible with your phone"` | **Android 14 bloqueia minSdkVersion < 23 via UI** | **minSdkVersion=26** |

**Insight:** O Android 14 (S23) bloqueia SILENCIOSAMENTE a instalação de APKs com `minSdkVersion` abaixo de 23 pelo instalador de pacotes. Não há mensagem de erro útil — apenas "incompatible". `minSdkVersion=26` (Android 8) resolve.

### Fase 6: Runtime

| # | Erro | Causa | Solução |
|---|------|-------|---------|
| 15 | Crash ao abrir (tela branca) | Sem tema definido + sem permissões runtime | `android:theme="@android:style/Theme.Material.Light"` |
| 16 | Crash ao conectar | BLUETOOTH_CONNECT não solicitado em runtime (Android 12+) | `requestPermissions(BLUETOOTH_CONNECT)` antes de conectar |
| 17 | Crash no startForegroundService | Sem FOREGROUND_SERVICE_CONNECTED_DEVICE (Android 14+) | Adicionar permissão no manifest |

**Insight:** Android 12+ exige `BLUETOOTH_CONNECT` em RUNTIME (não basta declarar no manifest). Sem isso, `createRfcommSocketToServiceRecord()` lança SecurityException. E Android 14+ exige `foregroundServiceType` explícito.

---

## 📋 Regras de Ouro (Build Android no Termux)

| # | Regra | Consequência se ignorar |
|---|-------|------------------------|
| 1 | **aapt2 + platform-33** (nunca 34+) | aapt2 não carrega o android.jar |
| 2 | **javac + platform-36** (API completa) | Funciona, mas platform-33 também funciona |
| 3 | **dx** (nunca d8) | Crash NPE em toda inner class |
| 4 | **--release 8** no javac | Java 21 não aceita source < 8 |
| 5 | **NUNCA usar lambdas** (`->`) | Erro de compilação: LambdaMetafactory |
| 6 | **minSdkVersion >= 26** | Android 14 bloqueia instalação |
| 7 | **android:exported** em Activity | "problem parsing the package" |
| 8 | **android:foregroundServiceType** | Crash no startForeground |
| 9 | **BLUETOOTH_CONNECT em runtime** | Crash ao criar socket Bluetooth |
| 10 | **FOREGROUND_SERVICE_CONNECTED_DEVICE** | Crash no startForegroundService |
| 11 | **Tema Material básico** | Crash ao iniciar Activity |
| 12 | **Usar named inner classes** em vez de anônimas | d8 crasha com ambas, dx funciona com ambas |
| 13 | **Paths absolutos** no script de build | apksigner não encontra arquivos |
| 14 | **Baixar SDK completo** (não framework.jar) | aapt não encontra attrs.xml |
| 15 | **Copiar classes.dex pro APK_DIR** antes do aapt add | classes.dex não incluído no APK |

---

## 🚀 Build (1 comando)

```bash
cd ~/bt_bridge_app && bash build.sh
```

**Pré-requisitos (1x):**
```bash
pkg install openjdk-21 aapt2 dx apksigner curl -y

# Baixar SDKs
cd ~/android-sdk
curl -LO "https://dl.google.com/android/repository/platform-33-ext5_r01.zip"
curl -LO "https://dl.google.com/android/repository/platform-36_r01.zip"
unzip -q platform-33-ext5_r01.zip -d platforms/android-33/
unzip -q platform-36_r01.zip -d platforms/android-36/
```

---

## 📱 Uso

```bash
# 1. Parear ESP32 via Bluetooth do Android
# 2. Abrir app "BT SPP Bridge" → tocar no ESP32
# 3. No Termux:
nc localhost 8090
# Enviar: TEMP?, STATUS, HELP
# Receber dados do ESP32
```

---

## 📦 Arquivos Finais

| Arquivo | Local | Descrição |
|---------|-------|-----------|
| APK | `/storage/emulated/0/bt-spp-bridge.apk` | App instalável (20 KB) |
| Código | `~/bt_bridge_app/` | Fonte completo + build script |
| ESP32 | `~/esp32_bt_temp.ino` | Código Arduino ESP32 SPP |
| Plano | `~/bt_bridge_app/PLANO.md` | 17 erros documentados |
| Review | `~/bt_bridge_app/REVIEW.json` | Análise JSON |

---

## 🎓 Insights Finais

1. **Build Android no Termux é VIÁVEL** — mas exige conhecer as incompatibilidades
2. **O ecossistema de ferramentas ARM64 é imaturo** — aapt2 limitado, d8 quebrado, dx legado
3. **Android 14 é muito mais restritivo** — permissões runtime, foregroundServiceType, minSdk mínimo
4. **O instalador de pacotes do Android é opaco** — mensagens de erro não ajudam, é preciso testar cada hipótese
5. **A estratégia de 2 SDKs funcionou** — platform-33 pra recursos, platform-36 pra compilação
6. **15 regras de ouro** documentadas — qualquer desvio causa falha

**Tempo total de desenvolvimento:** ~3 horas
**APK final:** 20 KB, funcional, zero dependências externas

---

## ✅ ATUALIZAÇÃO FINAL: Conexão T470 ↔ S23 (2026-06-10)

### Fase 7: Scan e Conexão Real

| # | Erro | Causa | Solução |
|---|------|-------|---------|
| 18 | Scan não retorna nada | `ACCESS_FINE_LOCATION` não solicitada | `requestPermissions(LOCATION)` |
| 19 | Não conecta no T470 | UUID SPP padrão reservado pelo BlueZ 5.86 | UUID custom + fallback canal RFCOMM via reflection |

### Arquitetura final de conexão (3 tentativas):

```
1. createRfcommSocketToServiceRecord(UUID_PADRAO) → SDP lookup
2. createRfcommSocketToServiceRecord(UUID_CUSTOM) → SDP lookup T470
3. createRfcommSocket(canal) via reflection → bypass SDP, scan canais 1-30
```

### ✅ Pipeline completo verificado:

```
Termux S23 ──nc :8090──> BridgeService ──Bluetooth SPP (canal 4)──> T470 spp_server.py
                                                                      ↓
                                                                  stdout
```

T470 recebeu: `teste s23` ✅

---

## 📊 Métricas Finais

| Métrica | Valor |
|---------|-------|
| Erros resolvidos | **19** |
| Regras de ouro | **15** |
| Arquivos do projeto | 8 (PLANO, SUCESSO, GUIA_T470, REVIEW, build.sh, MainActivity, BridgeService, Manifest) |
| APK final | 20 KB |
| Build | 1 comando |
| Conexão S23↔T470 | ✅ Estabelecida |
| Suporte ESP32 | ✅ Mesmo UUID padrão |

**PROJETO CONCLUÍDO COM SUCESSO.**

## 📎 Documentos relacionados
- [README.md](../README.md) — Guia de build
- [PLANO.md](PLANO.md) — Histórico de erros
- [GUIA_T470.md](GUIA_T470.md) — Servidor SPP Linux
- [REVIEW.json](REVIEW.json) — Análise estruturada
