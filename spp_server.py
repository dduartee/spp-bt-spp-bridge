#!/usr/bin/env python3
"""SPP Server — T470 Bluetooth Serial Port Profile.

Bridge bidirecional: stdin/stdout ↔ Bluetooth RFCOMM.

Uso:
  python3 spp_server.py              # modo completo (SDP + socket)
  python3 spp_server.py --no-sdp     # raw socket, sem registro BlueZ
"""

import argparse
import sys
import time
import threading

from spp_common import (
    ADAPTER_ADDR,
    RFCOMM_CHANNEL,
    SPP_UUID,
    SERVICE_NAME,
    bridge,
    create_rfcomm_server,
    register_sdp,
    unregister_sdp,
    _print,
)


def main():
    parser = argparse.ArgumentParser(description="SPP Server — T470 Bluetooth")
    parser.add_argument("--no-sdp", action="store_true",
                        help="Pular registro SDP no BlueZ (raw socket apenas)")
    args = parser.parse_args()

    manager = None
    glib_loop = None

    # 1. RFCOMM socket
    _print(f"🔌 Criando socket RFCOMM canal {RFCOMM_CHANNEL}...")
    server = create_rfcomm_server()
    _print(f"✅ Socket ouvindo em {ADAPTER_ADDR}:{RFCOMM_CHANNEL}")

    # 2. SDP (opcional)
    if not args.no_sdp:
        _print(f"🔧 Registrando SDP: '{SERVICE_NAME}'")
        manager, glib_loop = register_sdp()
        _print(f"✅ SDP registrado (UUID: {SPP_UUID})")

    # 3. Info
    _print("")
    _print("=" * 60)
    _print("📱 Dados para conectar do Android:")
    _print(f"   MAC:   {ADAPTER_ADDR}")
    _print(f"   Canal: {RFCOMM_CHANNEL}")
    _print(f"   UUID:  {SPP_UUID}")
    _print("=" * 60)
    _print("")
    _print("⏳ Aguardando conexão do Android...")
    _print("   (Ctrl+C para encerrar)")
    _print("")

    # 4. Loop de conexões
    conn_count = 0
    try:
        while True:
            try:
                client, addr = server.accept()
                conn_count += 1
                _print(f"\n✅ Conectado (#{conn_count}): {addr}")
                bridge(client, f" (#{conn_count})")
                _print(f"🔌 Conexão #{conn_count} encerrada. Re-aguardando...\n")
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                _print(f"⚠️  Erro: {exc}")
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        _print("\n🛑 Encerrando...")
        if manager is not None and glib_loop is not None:
            unregister_sdp(manager, glib_loop)
        server.close()
        _print("👋 Servidor fechado")


if __name__ == "__main__":
    main()
