# 🔵 BT SPP Bridge — Proof of Concept

> **Comunicação Bluetooth SPP via Android + Termux + Linux, com desenvolvimento assistido por IA.**
>
> Android app nativo (build no Termux, sem PC) atua como ponte Bluetooth ↔ TCP.
> Permite que o Termux leia/escreva dados de qualquer dispositivo Bluetooth SPP
> (ESP32, sensores, outro notebook) via `nc localhost 8090`.

---

## 🎯 Conceito

```
┌──────────────┐   Bluetooth SPP    ┌─────────────────┐   TCP :8090    ┌──────────┐
│  ESP32       │◄──────────────────►│  S23 (Android)   │◄─────────────►│  Termux  │
│  sensor temp │   RFCOMM UUID      │  BT SPP Bridge   │  localhost     │  nc / py │
└──────────────┘                    │  (Foreground Svc)│                └──────────┘
                                    └────────┬────────┘
                                             │
                                    Bluetooth SPP (canal 4)
                                             │
                                    ┌────────▼────────┐
                                    │  T470 (Linux)    │
                                    │  spp_server.py   │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  AI Agent (pi)   │
                                    │  stdin/stdout    │
                                    └─────────────────┘
```

**Fluxo:** Dados trafegam bidirecionalmente entre qualquer ponta — o app Android é o hub central que traduz Bluetooth ↔ TCP.

---

## 📦 Estrutura do Projeto

```
spp-t470/                          ← repositório raiz
│
├── README.md                      ← este documento
├── SUCCESS_REPORT.md              ← relatório de debug T470↔S23
│
├── 🐧 LADO T470 (Linux) ─────────────────────────────────
│   ├── spp_common.py              ← bridge(), constantes, helpers
│   ├── spp_server.py              ← servidor SPP (--no-sdp p/ raw)
│   ├── spp_client.py              ← modo reverso (T470→S23)
│   └── setup_bt.py                ← prepara adapter Bluetooth
│
└── 📱 LADO S23 (Android/Termux) ─────────────────────────
    └── bt-spp-bridge/
        ├── README.md              ← guia de build no Termux
        ├── TERMUX_API_GUIA.md     ← referência Termux:API
        ├── esp32_bt_temp.ino      ← teste ESP32 Bluetooth
        └── app/
            ├── build.sh           ← build do APK (1 comando)
            ├── PLANO.md           ← log de desenvolvimento (18 erros)
            ├── SUCESSO.md         ← documentação completa
            ├── REVIEW.json        ← análise estruturada (JSON)
            ├── GUIA_T470.md       ← guia original do servidor
            └── app/src/main/
                ├── AndroidManifest.xml
                ├── res/values/strings.xml
                └── java/com/termux/bridge/
                    ├── MainActivity.java      ← UI (lista + scan)
                    └── BridgeService.java     ← foreground service
```

---

## 🚀 Uso Rápido

### 1. T470 — Servidor SPP

```bash
cd spp-t470
python3 setup_bt.py          # garantir discoverable (1x)
python3 spp_server.py        # iniciar servidor
```

### 2. S23 — App + Termux

```bash
# No Termux: build e instala o APK
cd ~/projetos/bt-spp-bridge/app
bash build.sh                # gera bt-spp-bridge.apk
# Instalar pelo gerenciador de arquivos

# Abrir BT SPP Bridge → escanear → tocar no t470
# No Termux:
nc localhost 8090            # bridge ativa!
```

### 3. Teste bidirecional

```
Termux:  digita "hello do s23"  → aparece no terminal T470 ✅
T470:    digita "oi do t470"    → aparece no nc do Termux ✅
```

---

## 🧠 Desenvolvimento Assistido por IA

Todo o projeto foi implementado por **agentes pi** trabalhando em paralelo:

```
┌─────────────────────────────────────────────────────┐
│                 ORQUESTRADOR (pi)                    │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Agente T470  │  │ Agente S23   │  │ Reviewer    │ │
│  │ (Linux/SPP)  │  │ (Android)    │  │ (fanout)    │ │
│  │              │  │              │  │             │ │
│  │ spp_server   │  │ APK build    │  │ integração  │ │
│  │ debug BT     │  │ Termux java  │  │ docs        │ │
│  │ bridge I/O   │  │ Permissions  │  │ revisão     │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬───────┘ │
│         │                 │                 │         │
│         └─────────┬───────┘                 │         │
│                   │                         │         │
│            ┌──────▼──────┐                  │         │
│            │  INTERCOM   │◄─────────────────┘         │
│            │  relatórios │                             │
│            │  debug logs │                             │
│            └─────────────┘                             │
└─────────────────────────────────────────────────────┘
```

### Agentes envolvidos

| Agente | Responsabilidade | Artefatos |
|--------|-----------------|-----------|
| **T470 (Linux)** | Servidor SPP, raw sockets, debug de I/O | `spp_server.py`, `SUCCESS_REPORT.md` |
| **S23 (Android)** | APK nativo no Termux, build, permissões, UI | `MainActivity.java`, `BridgeService.java`, `build.sh` |
| **Reviewer (fanout)** | Análise de erros, documentação, integração | `PLANO.md`, `REVIEW.json`, `README.md` |

### Comunicação entre agentes

- **Intercom** — relatórios de debug, descobertas, handoffs
- **SCP via SSH** — transferência de arquivos entre dispositivos
- **Markdown** — documentação viva atualizada a cada iteração

---

## 🔧 Stack Técnica

### Lado T470 (Linux)

| Camada | Tecnologia | Detalhe |
|--------|-----------|---------|
| Socket | `AF_BLUETOOTH` + `BTPROTO_RFCOMM` | Raw socket do kernel Linux |
| SDP | `org.bluez.ProfileManager1` (D-Bus) | Registro de perfil no BlueZ 5.86 |
| Bridge | 2 threads bloqueantes | `os.read()` + `sock.recv()/send()` |
| Runtime | Python 3.14 | Manjaro Linux, kernel 6.12 |

### Lado S23 (Android/Termux)

| Camada | Tecnologia | Detalhe |
|--------|-----------|---------|
| Build | `aapt2` + `javac` + `dx` + `apksigner` | 100% nativo no Termux ARM64 |
| Bluetooth | `BluetoothSocket.createRfcommSocket()` | Reflection + fallback por canal |
| TCP Server | `ServerSocket :8090` | Foreground service |
| UI | `LinearLayout` programático | Botões dinâmicos via `HashMap<View, Device>` |
| SDK | platform-33 (aapt2) + platform-36 (javac) | SDKs baixados via curl no Termux |

### Ponte de conexão

| Método | Status | Motivo |
|--------|--------|--------|
| SDP UUID padrão (`00001101`) | ❌ | BlueZ reserva internamente |
| SDP UUID custom (`977c4a04`) | ❌ | SDP discovery não encontrou |
| Raw RFCOMM canal 4 (reflection) | ✅ | `createRfcommSocket(4)` via reflection |

---

## 🐛 Bugs Resolvidos (18 erros)

### Lado T470 (5 bugs)

| # | Bug | Correção |
|---|-----|----------|
| 1 | `socket.read()` não existe | `socket.recv()` |
| 2 | `select()` + `sys.stdin.buffer` (thread) | `os.read("/dev/stdin")` bloqueante |
| 3 | dbus-python 1.4 não exporta objetos (Python 3.14) | raw socket sem callback D-Bus |
| 4 | BlueZ 5.86 reserva UUID `0x1101` | UUID custom `977c4a04-...` |
| 5 | `socket.write()` não existe | `socket.send()` |

### Lado S23 (13 bugs — ver `PLANO.md`)

| Categoria | Exemplos |
|-----------|----------|
| Build | aapt2 + platform-36 incompatível, d8 bugado, minSdkVersion < 26 |
| Permissões | `BLUETOOTH_CONNECT`, `ACCESS_FINE_LOCATION`, `POST_NOTIFICATIONS` |
| Android 14 | `android:exported`, `foregroundServiceType`, `SecurityException` |
| Java | Lambdas (`->`) quebram no Android SDK, usar classes anônimas |
| SDP | UUID padrão reservado → fallback raw RFCOMM channel |

---

## 📊 Especificações do APK

| Atributo | Valor |
|----------|-------|
| Package | `com.termux.bridge` |
| Tamanho | ~17 KB |
| minSdkVersion | 26 (Android 8+) |
| targetSdkVersion | 33 |
| Permissões | Bluetooth×4, Location×2, Internet, Foreground×2, Notifications |

---

## 🔗 Referências

- [`bt-spp-bridge/README.md`](bt-spp-bridge/README.md) — Guia completo de build no Termux
- [`bt-spp-bridge/app/PLANO.md`](bt-spp-bridge/app/PLANO.md) — Log de desenvolvimento (18 erros)
- [`bt-spp-bridge/app/SUCESSO.md`](bt-spp-bridge/app/SUCESSO.md) — Documentação completa
- [`bt-spp-bridge/app/REVIEW.json`](bt-spp-bridge/app/REVIEW.json) — Análise estruturada
- [`SUCCESS_REPORT.md`](SUCCESS_REPORT.md) — Relatório de debug T470↔S23
- [`bt-spp-bridge/TERMUX_API_GUIA.md`](bt-spp-bridge/TERMUX_API_GUIA.md) — Referência Termux:API
