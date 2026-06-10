#!/usr/bin/env python3
"""SPP Client — T470 conecta ao Android (modo reverso).

Quando o S23 está rodando BT SPP Bridge como servidor,
este script conecta ao S23 e faz bridge stdin/stdout.

Uso:
  S23_MAC=64:1B:2F:31:20:48 SPP_CHANNEL=4 python3 spp_client.py
"""

import os
import sys
import time

from spp_common import (
    RFCOMM_CHANNEL,
    bridge,
    connect_rfcomm,
    _print,
)

# Configuração via variáveis de ambiente (sem hardcoded MACs)
S23_MAC = os.environ.get("S23_MAC", "")
SPP_CHANNEL = int(os.environ.get("SPP_CHANNEL", str(RFCOMM_CHANNEL)))


def main():
    if not S23_MAC:
        _print("❌ S23_MAC não definido.")
        _print("   Uso: S23_MAC=XX:XX:XX:XX:XX:XX python3 spp_client.py")
        _print("   Opcional: SPP_CHANNEL=N (default: 4)")
        sys.exit(1)

    _print(f"🔌 Conectando ao S23 ({S23_MAC}) canal {SPP_CHANNEL}...")

    try:
        sock = connect_rfcomm(S23_MAC, SPP_CHANNEL)
        _print("✅ Conectado ao S23!")
        bridge(sock, " (cliente)")
    except OSError as exc:
        _print(f"❌ Erro ao conectar: {exc}")
        _print(f"   Verifique se o BT SPP Bridge está rodando no S23")
        _print(f"   MAC do S23: {S23_MAC}")
        _print(f"   Canal: {SPP_CHANNEL}")
        _print("")
        _print("   Para configurar MAC diferente:")
        _print("   S23_MAC=XX:XX:XX:XX:XX:XX SPP_CHANNEL=N python3 spp_client.py")
    finally:
        try:
            sock.close()
        except Exception:
            pass
        _print("👋 Desconectado")


if __name__ == "__main__":
    main()
