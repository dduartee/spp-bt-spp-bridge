# 🖥️ Guia: Servidor SPP Bluetooth no T470 (Linux)

> Para outro agente pi implementar sem contexto prévio.
> Objetivo: Fazer o notebook T470 (Linux) aparecer como dispositivo SPP
> para o app BT SPP Bridge no Android S23 conectar.

---

## 🎯 Objetivo

Criar um servidor Bluetooth SPP (Serial Port Profile) no T470 que:
1. Registra um serviço SPP (UUID: `00001101-0000-1000-8000-00805F9B34FB`)
2. Aguarda conexão do app Android "BT SPP Bridge"
3. Bridge bidirecional: dados do Bluetooth ↔ stdin/stdout
4. Quando o app Android conecta, o T470 pode enviar/receber dados

---

## 📋 Requisitos

- Linux (T470)
- Bluetooth funcional (`bluetoothctl` mostra o adaptador)
- Python 3 com `pybluez` ou `bluez` stack nativa
- Permissão sudo (para `rfcomm` e `sdptool`)

---

## 🔧 Opção A: Python + PyBluez (Recomendado)

### Instalação:
```bash
sudo apt install python3-pip libbluetooth-dev -y
pip install pybluez
```

### Script: `~/spp_server.py`
```python
#!/usr/bin/env python3
"""
SPP Server no T470 — aguarda conexão do app BT SPP Bridge (Android).
Bridge bidirecional: Bluetooth ↔ stdin/stdout.
"""
import sys
import threading
from bluetooth import *

# UUID padrão SPP (mesmo do app Android)
SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"
SERVICE_NAME = "T470-SPP"

def handle_client(client_sock):
    """Bridge: Bluetooth → stdout (thread separada)"""
    try:
        while True:
            data = client_sock.recv(1024)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.flush()
    except Exception:
        pass

def main():
    server_sock = BluetoothSocket(RFCOMM)
    server_sock.bind(("", PORT_ANY))
    server_sock.listen(1)

    port = server_sock.getsockname()[1]
    print(f"📡 Servidor SPP: canal {port}")

    # Anuncia serviço SPP (para aparecer na lista do Android)
    advertise_service(
        server_sock,
        SERVICE_NAME,
        service_id=SPP_UUID,
        service_classes=[SPP_UUID, SERIAL_PORT_CLASS],
        profiles=[SERIAL_PORT_PROFILE]
    )
    print(f"🔍 Anunciado como '{SERVICE_NAME}'")
    print(f"⏳ Aguardando conexão do app Android...")

    client_sock, client_info = server_sock.accept()
    print(f"✅ Conectado: {client_info}")

    # Thread: Bluetooth → stdout
    reader = threading.Thread(target=handle_client, args=(client_sock,), daemon=True)
    reader.start()

    # Thread principal: stdin → Bluetooth
    try:
        while True:
            data = sys.stdin.buffer.read(1024)
            if not data:
                break
            client_sock.send(data)
    except KeyboardInterrupt:
        print("\n👋 Desconectado")
    finally:
        client_sock.close()
        server_sock.close()

if __name__ == "__main__":
    main()
```

### Uso:
```bash
chmod +x ~/spp_server.py
python3 ~/spp_server.py

# No Android: abrir BT SPP Bridge → tocar em "T470-SPP"
# No Termux do S23 (via SSH): nc localhost 8090
```

---

## 🔧 Opção B: BlueZ nativo (sdptool + rfcomm)

### Instalação:
```bash
sudo apt install bluez bluez-tools -y
```

### Script: `~/spp_server.sh`
```bash
#!/bin/bash
# SPP Server via bluez nativo

SERVICE_NAME="T470-SPP"
SPP_UUID="00001101-0000-1000-8000-00805F9B34FB"
CHANNEL=1

echo "🔧 Registrando serviço SPP..."
sudo sdptool add --channel=$CHANNEL SP

echo "📡 Aguardando conexão no canal $CHANNEL..."
echo "   No Android: abrir BT SPP Bridge → tocar em '$SERVICE_NAME'"

# rfcomm listen bloqueia até receber conexão
sudo rfcomm listen 0 $CHANNEL

# Após conexão, dados fluem via /dev/rfcomm0
echo "✅ Conectado! Bridge em /dev/rfcomm0"
echo "   Ler: cat /dev/rfcomm0"
echo "   Escrever: echo 'teste' > /dev/rfcomm0"
```

### Uso:
```bash
chmod +x ~/spp_server.sh
bash ~/spp_server.sh
```

---

## 🔧 Opção C: Script ultra-simples (apenas echo)

Se quiser só testar conectividade sem bridge complexa:

```python
#!/usr/bin/env python3
from bluetooth import *
import time

server = BluetoothSocket(RFCOMM)
server.bind(("", PORT_ANY))
server.listen(1)

advertise_service(server, "T470-Test",
    service_id="00001101-0000-1000-8000-00805F9B34FB",
    service_classes=["00001101-0000-1000-8000-00805F9B34FB", SERIAL_PORT_CLASS],
    profiles=[SERIAL_PORT_PROFILE])

print("⏳ Aguardando...")
client, addr = server.accept()
print(f"✅ Conectado: {addr}")

# Envia heartbeat a cada 2 segundos
for i in range(30):
    client.send(f"T470 heartbeat {i}\n".encode())
    time.sleep(2)

client.close()
server.close()
```

---

## 🔄 Fluxo Completo

```
┌──────────┐   Bluetooth SPP    ┌──────────────┐   TCP :8090    ┌──────────┐
│   T470   │ ◄────────────────► │  BT SPP       │ ◄───────────► │  Termux  │
│ (Python) │    RFCOMM UUID     │  Bridge (S23) │   localhost   │ (nc/py)  │
└──────────┘                     └──────────────┘                └──────────┘

Fluxo:
1. T470: python3 spp_server.py → anuncia "T470-SPP"
2. S23: App BT SPP Bridge → lista "T470-SPP" → toca → conecta
3. S23: BridgeService → TCP server :8090
4. S23 Termux: nc localhost 8090
5. Dados fluem: Termux ↔ TCP ↔ Bluetooth ↔ T470 Python
```

---

## 🧪 Teste

### Terminal 1 (T470):
```bash
python3 ~/spp_server.py
# Saída esperada:
# 📡 Servidor SPP: canal 1
# 🔍 Anunciado como 'T470-SPP'
# ⏳ Aguardando conexão do app Android...
```

### Terminal 2 (S23, via SSH):
```bash
# Depois de conectar o app:
nc localhost 8090
# Digita "hello from termux"
```

### Terminal 1 (T470):
```
✅ Conectado: ('XX:XX:XX:XX:XX:XX', 1)
hello from termux    ← aparece aqui!
```

---

## ⚠️ Troubleshooting

| Problema | Solução |
|----------|---------|
| `bluetooth.error: no advertisable device` | `sudo hciconfig hci0 piscan` |
| Dispositivo não aparece no Android | Repareie o T470 nas configs Bluetooth |
| `Permission denied` no rfcomm | Precisa de `sudo` |
| `pybluez` não instala | `sudo apt install libbluetooth-dev` |
| App conecta mas nc não responde | Verifique `nc localhost 8090` no S23 |

---

## 🔗 Ref: INVESTIGACAO_T470.md (fundido aqui)

### Checkpoints de Debug

#### T470 → S23 não funcionando?

Verifique no Python:
1. `stdin` está sendo lido? Tem `sys.stdin.read()` ou `input()`?
2. `client.send(data)` usa o MESMO socket do `accept()`?
3. O `send()` está dentro do loop principal (não em thread que morreu)?
4. `send()` retorna > 0 bytes?
5. `client.getpeername()` ainda retorna o endereço do S23?

#### Teste rápido
No terminal do servidor SPP, digite algo. Se NÃO aparece no `nc` do S23:
→ O `send()` não está sendo chamado ou está no socket errado.


## 📎 Documentos relacionados
- [README.md](../README.md) — Guia de build do APK
- [PLANO.md](PLANO.md) — Histórico de erros do build
- [SUCESSO.md](SUCESSO.md) — Documentação completa
