# ✅ Relatório Final — SPP T470 ↔ S23

## Status: FUNCIONANDO 100% bidirecional

```
T470 (F4:96:34:60:D6:3B) ←→ S23 (64:1B:2F:31:20:48)
         canal RFCOMM 4

S23 → T470: ✅  T470 → S23: ✅
```

---

## O que foi testado e funcionou

| Teste | Resultado |
|-------|-----------|
| S23 nc → T470 stdout | ✅ "s23 envia ok" apareceu |
| T470 stdin → S23 nc | ✅ "t470 envia oi" apareceu |
| Handshake automático | ✅ "🤝 T470 handshake" apareceu |
| Reconexão após queda | ✅ loop ativo (re-accept) |

---

## Método de conexão (lado Android)

| Camada | UUID/Método | Resultado |
|--------|-------------|-----------|
| 1 | UUID padrão `00001101-...` | ❌ BlueZ reserva |
| 2 | UUID custom `977c4a04-...` | ❌ SDP não achou |
| 3 | `createRfcommSocket(4)` reflection | ✅ FUNCIONOU |

---

## Stack técnica (lado T470)

- **Socket:** `AF_BLUETOOTH` + `BTPROTO_RFCOMM` (kernel Linux)
- **SDP:** `ProfileManager1.RegisterProfile` (BlueZ D-Bus)
- **Bridge:** 2 threads bloqueantes
  - Thread A: `sock.recv()` → `stdout` (S23 → T470)
  - Thread B: `os.read("/dev/stdin")` → `sock.send()` (T470 → S23)
- **Reconexão:** loop infinito com `server.accept()`

---

## Bugs encontrados e corrigidos

| # | Bug | Sintoma | Correção |
|---|-----|---------|----------|
| 1 | `socket.read()` não existe | `AttributeError` crash | `socket.recv()` |
| 2 | `select()` + `sys.stdin.buffer` | stdin nunca lido em thread | `os.read(fd)` bloqueante |
| 3 | dbus-python 1.4 não exporta objetos | Profile1 callback vazio | raw socket sem callback |
| 4 | BlueZ 5.86 reserva UUID `0x1101` | `UUID already registered` | UUID custom |
| 5 | `socket.write()` não existe | `AttributeError` | `socket.send()` |

---

## Dados de conexão

```
MAC T470:  F4:96:34:60:D6:3B
Canal:     4
UUID SDP:  977c4a04-bf68-4c23-bf49-dac84b22d774
Nome SDP:  T470-SPP
```

## Comando

```bash
cd ~/spp-t470 && python3 spp_server.py
```
