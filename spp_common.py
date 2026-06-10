"""Shared utilities for SPP bridge scripts.

Constants and the canonical bridge() implementation.
"""

import os
import sys
import socket
import threading

# ── Bluetooth adapter ──────────────────────────────────────
ADAPTER_ADDR = "F4:96:34:60:D6:3B"
RFCOMM_CHANNEL = 4

# ── SDP / BlueZ ────────────────────────────────────────────
SPP_UUID = "977c4a04-bf68-4c23-bf49-dac84b22d774"
SERVICE_NAME = "T470-SPP"
PROFILE_PATH = "/bluetooth/profile/spp_t470"
SERVICE_RECORD = f"""<?xml version="1.0" encoding="UTF-8" ?>
<record>
  <attribute id="0x0001">
    <sequence>
      <uuid value="{SPP_UUID}"/>
    </sequence>
  </attribute>
  <attribute id="0x0004">
    <sequence>
      <sequence>
        <uuid value="0x0100"/>
      </sequence>
      <sequence>
        <uuid value="0x0003"/>
        <uint8 value="{RFCOMM_CHANNEL}" name="channel"/>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0100">
    <text value="{SERVICE_NAME}" name="name"/>
  </attribute>
</record>"""

# ── I/O buffers ────────────────────────────────────────────
BUFFER_SIZE = 4096
JOIN_TIMEOUT = 1.0

# ── stdout lock (prevents garbled output from 2 threads) ──
_stdout_lock = threading.Lock()


def _write_stdout(data):
    """Thread-safe write to stdout."""
    with _stdout_lock:
        sys.stdout.buffer.write(data)
        sys.stdout.flush()


def _print(msg, **kwargs):
    """Thread-safe print to stdout."""
    with _stdout_lock:
        print(msg, flush=True, **kwargs)


# ── Bridge ─────────────────────────────────────────────────

def bridge(sock, label=""):
    """Bridge bidirecional: Bluetooth RFCOMM ↔ stdin/stdout.

    Thread A: sock.recv() → stdout  (remote → local)
    Thread B: os.read(stdin) → sock.send()  (local → remote)

    Usa os.read() em fd raw porque sys.stdin.buffer.read()
    não funciona corretamente em thread separada no Python 3.14.
    """
    running = threading.Event()
    running.set()

    def bt_to_stdout():
        """Thread A: Bluetooth → stdout."""
        try:
            while running.is_set():
                try:
                    data = sock.recv(BUFFER_SIZE)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    break
                if not data:
                    break
                _write_stdout(data)
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)
        finally:
            running.clear()

    def stdin_to_bt():
        """Thread B: stdin → Bluetooth."""
        stdin_fd = -1
        try:
            stdin_fd = os.open("/dev/stdin", os.O_RDONLY)
            while running.is_set():
                data = os.read(stdin_fd, BUFFER_SIZE)
                if not data:
                    break
                try:
                    sock.send(data)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    break
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)
        finally:
            running.clear()
            if stdin_fd >= 0:
                try:
                    os.close(stdin_fd)
                except OSError:
                    pass

    t_bt = threading.Thread(target=bt_to_stdout, daemon=True)
    t_in = threading.Thread(target=stdin_to_bt, daemon=True)
    t_bt.start()
    t_in.start()

    _print(f"📡 Bridge ativa{label}. stdin→BT, BT→stdout. Ctrl+C p/ sair.\n")

    try:
        while running.is_set():
            t_bt.join(timeout=0.5)
            t_in.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        running.clear()
        t_bt.join(timeout=JOIN_TIMEOUT)
        t_in.join(timeout=JOIN_TIMEOUT)
        try:
            sock.close()
        except OSError:
            pass


# ── RFCOMM socket helpers ──────────────────────────────────

def create_rfcomm_server(addr=ADAPTER_ADDR, channel=RFCOMM_CHANNEL):
    """Cria e retorna um socket RFCOMM ouvindo."""
    server = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                           socket.BTPROTO_RFCOMM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((addr, channel))
    server.listen(1)
    return server


def connect_rfcomm(addr, channel=RFCOMM_CHANNEL):
    """Conecta a um servidor RFCOMM remoto."""
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                         socket.BTPROTO_RFCOMM)
    sock.connect((addr, channel))
    return sock


# ── BlueZ D-Bus SDP ────────────────────────────────────────

def register_sdp():
    """Registra perfil SPP no BlueZ via D-Bus ProfileManager1.

    Retorna (manager, glib_loop) para desregistrar depois.
    """
    import dbus
    import dbus.mainloop.glib
    from gi.repository import GLib

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    manager = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"),
        "org.bluez.ProfileManager1")

    opts = {
        "Name": SERVICE_NAME,
        "ServiceRecord": SERVICE_RECORD,
        "Role": "server",
        "AutoConnect": True,
        "Channel": dbus.UInt16(RFCOMM_CHANNEL),
        "RequireAuthentication": False,
        "RequireAuthorization": False,
    }

    manager.RegisterProfile(PROFILE_PATH, SPP_UUID, opts)

    glib_loop = GLib.MainLoop()
    threading.Thread(target=glib_loop.run, daemon=True).start()

    return manager, glib_loop


def unregister_sdp(manager, glib_loop):
    """Remove perfil SPP do BlueZ."""
    glib_loop.quit()
    try:
        manager.UnregisterProfile(PROFILE_PATH)
    except Exception:
        pass
