#!/usr/bin/env python3
"""Prepara o Bluetooth do T470 para receber conexões SPP.

Torna o adaptador discoverable e pairable permanentemente.
Rode uma vez antes de usar spp_server.py.
"""

import sys
import dbus
import dbus.mainloop.glib


def main():
    try:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()
    except dbus.DBusException as exc:
        sys.exit(f"❌ Erro D-Bus: {exc}\n   O bluetoothd está rodando?")

    adapter = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez/hci0"),
        "org.freedesktop.DBus.Properties",
    )

    try:
        adapter.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
        adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
        adapter.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
        adapter.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
    except dbus.DBusException as exc:
        sys.exit(f"❌ Erro ao configurar adapter: {exc}")

    name = adapter.Get("org.bluez.Adapter1", "Name")
    addr = adapter.Get("org.bluez.Adapter1", "Address")
    disc = adapter.Get("org.bluez.Adapter1", "Discoverable")
    pair = adapter.Get("org.bluez.Adapter1", "Pairable")

    print(f"✅ Bluetooth pronto: {name} ({addr})")
    print(f"   Discoverable: {disc}")
    print(f"   Pairable: {pair}")
    print()
    print("🔍 O T470 está visível para pareamento.")
    print("   No Android: Settings → Bluetooth → pareie com 't470'")


if __name__ == "__main__":
    main()
