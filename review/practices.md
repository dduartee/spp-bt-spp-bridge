# Code Practices Review — `spp-t470`

**Date:** 2026-06-10  
**Files reviewed:** `spp_server.py`, `spp_client.py`, `spp_simple.py`, `setup_bt.py`  
**Excluded from scope:** Logic correctness (the code works).

---

## Findings Summary

| # | Category | Severity | File(s) |
|---|----------|----------|---------|
| 1 | Bare except / swallowed exceptions | **Critical** | spp_server.py |
| 2 | Bare except / swallowed exceptions | **High** | spp_server.py, spp_client.py, spp_simple.py |
| 3 | Code duplication — identical `bridge()` | **High** | spp_client.py, spp_simple.py |
| 4 | Code duplication — server socket setup | **Medium** | spp_server.py, spp_simple.py |
| 5 | Race condition: stdout writes from multiple threads | **High** | spp_server.py |
| 6 | dbus-python thread safety (shared connection) | **Medium** | spp_server.py |
| 7 | Possible unbound variable in `finally` | **Medium** | spp_simple.py |
| 8 | `os.open` failure → unbound `stdin_fd` in finally | **Low** | spp_server.py |
| 9 | `socket.read()`/`write()`/`flush()` do not exist | **Critical** | spp_client.py, spp_simple.py |
| 10 | No error handling at all | **Medium** | setup_bt.py |
| 11 | PEP 8: comma-separated imports | **Low** | spp_server.py, spp_client.py, spp_simple.py |
| 12 | Magic numbers (buffer sizes, timeouts) | **Low** | all files |
| 13 | `import time` inside except block | **Low** | spp_server.py |
| 14 | Missing `if __name__ == "__main__"` guard | **Low** | setup_bt.py |
| 15 | Inconsistent socket I/O: `recv`/`send` (correct) vs `read`/`write` (non-existent) | **High** | cross-file |

---

## Detailed Findings

### #1 — Critical: Bare `except Exception: pass` swallows all errors silently

**Files:** `spp_server.py` lines 81-82, 99-101, 104-106, 111-113

```python
# spp_server.py — bt_to_stdout() thread
except Exception:
    pass
```

```python
# spp_server.py — stdin_to_bt() thread
except Exception:
    pass
finally:
    running.clear()
    try:
        os.close(stdin_fd)
    except Exception:
        pass
```

**Problem:** These catch-all blocks silently discard *every* exception, including bugs like `AttributeError`, `TypeError`, or `NameError`. If `sys.stdout.buffer.write()` raises a `TypeError` (e.g., because `data` was `None`), the thread dies silently, `running` is cleared, and the bridge stops with zero diagnostic output. The developer has no way to know *why* the bridge failed.

**Fix:** At minimum, log the traceback before swallowing:

```python
except Exception:
    import traceback
    traceback.print_exc(file=sys.stderr)
```

Better: catch only the *expected* exceptions (`OSError`, `BrokenPipeError`, `ConnectionResetError`) and let unexpected ones propagate (the `finally` block will still clean up `running`).

---

### #2 — High: Broad exception suppression in bridge threads

**Files:** `spp_server.py` bt_to_stdout (line 81), `spp_client.py` bt_to_stdout (line ~38), `spp_simple.py` bt_to_stdout (line ~38)

The `bt_to_stdout` thread in all three files catches exceptions with no logging:

| File | Catches | Effect |
|------|---------|--------|
| spp_server.py | `except Exception: pass` | All errors vanish |
| spp_client.py | `except (OSError, ValueError): pass` | Better, but `ValueError` not justified |
| spp_simple.py | `except (OSError, ValueError): pass` | Same as client |

**Why `ValueError`?** The code catches `ValueError` alongside `OSError`. `select.select()` can raise `ValueError` if a negative timeout is passed or if a file descriptor is invalid. An invalid fd would be a programming bug, not a recoverable runtime condition. Silently swallowing it hides the bug.

**Fix:** Remove `ValueError` from the catch list. If `select` is given a bad fd, the program *should* crash with a traceback so the bug gets fixed.

---

### #3 — High: Identical `bridge()` function in two files (copy-paste duplication)

**Files:** `spp_client.py` lines 21-55, `spp_simple.py` lines 33-66

The `bridge()` function is **character-for-character identical** in both files:

```python
def bridge(rfcomm):
    """Bridge bidirecional: Bluetooth ↔ stdin/stdout"""
    running = threading.Event()
    running.set()

    def bt_to_stdout():
        try:
            while running.is_set():
                ready, _, _ = select.select([rfcomm], [], [], 0.5)
                if ready:
                    data = rfcomm.read(1024)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.flush()
        except (OSError, ValueError):
            pass
        finally:
            running.clear()

    reader = threading.Thread(target=bt_to_stdout, daemon=True)
    reader.start()
    # ... rest identical ...
```

Two copies of the same 35-line function means any bug fix must be applied in both places. They will inevitably diverge.

**Fix:** Extract into a shared module (`bridge.py` or `spp_common.py`) imported by both. This also gives a natural home for shared constants (buffer sizes, timeouts).

**Note:** The `bridge()` in `spp_server.py` is *different* by design (uses `os.read()` + separate stdin thread because `sys.stdin.buffer.read()` doesn't work in a background thread on Python 3.14). That variant could still share the `bt_to_stdout` logic.

---

### #4 — Medium: Duplicated RFCOMM socket setup

**Files:** `spp_server.py` lines 121-125, `spp_simple.py` lines 73-77

```python
# Both files:
server = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                       socket.BTPROTO_RFCOMM)
server.bind((ADAPTER_ADDR, RFCOMM_CHANNEL))
server.listen(1)
```

The same ADAPTER_ADDR and RFCOMM_CHANNEL constants are defined separately in each file. If the MAC or channel changes, it must be updated in multiple places.

**Fix:** Centralize in a shared config module or at least share constants.

---

### #5 — High: Race condition on stdout writes

**File:** `spp_server.py`

Two execution contexts write to stdout concurrently:

1. **Thread `bt_to_stdout`** (line 76-77): `sys.stdout.buffer.write(data)` + `sys.stdout.flush()`
2. **Main thread** (lines 108, 121-131, etc.): `print(...)` calls

```python
# Thread A (background):
sys.stdout.buffer.write(data)   # writes raw bytes
sys.stdout.flush()

# Thread B (main, concurrently):
print(f"✅ Conectado (#{conn_count}): {addr}", flush=True)
```

Python's GIL guarantees individual bytecode operations are atomic, but `sys.stdout.buffer.write()` is a C-level call that may interleave with `print()` mid-output. Result: corrupted/mixed output on the terminal when data arrives from Bluetooth at the same moment a connection message prints.

**Fix:** Protect all stdout access with a `threading.Lock`:

```python
_stdout_lock = threading.Lock()

def bt_to_stdout():
    ...
    with _stdout_lock:
        sys.stdout.buffer.write(data)
        sys.stdout.flush()

# In main:
with _stdout_lock:
    print(f"✅ Conectado ...", flush=True)
```

---

### #6 — Medium: dbus-python connection shared across threads

**File:** `spp_server.py` lines 132-140

```python
# Main thread:
bus = dbus.SystemBus()
manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"),
                         "org.bluez.ProfileManager1")
manager.RegisterProfile(...)    # synchronous call — fine

glib_loop = GLib.MainLoop()
threading.Thread(target=glib_loop.run, daemon=True).start()  # daemon thread
...
finally:
    manager.UnregisterProfile(PROFILE_PATH)  # main thread, but loop is running
```

[dbus-python is not thread-safe](https://dbus.freedesktop.org/doc/dbus-python/). The same `bus` connection is:
- Created in the main thread
- Its GLib main loop runs in a daemon thread
- `UnregisterProfile()` is called from the main thread while the loop runs

This works in practice most of the time because `UnregisterProfile` is likely the last D-Bus call, but it's undefined behavior.

**Fix:** Call `glib_loop.quit()` *before* `UnregisterProfile()`, and `glib_loop.run()` will return in the daemon thread. Then `UnregisterProfile()` is safe. Or use the bus only from the GLib thread via `GLib.idle_add()`.

---

### #7 — Medium: `client` variable may be unbound in `finally`

**File:** `spp_simple.py` lines 79-94

```python
try:
    client, addr = server.accept()
    print(f"✅ Conectado: {addr}", flush=True)
    bridge(client)
except KeyboardInterrupt:
    print("\n🛑 Encerrando...", flush=True)
finally:
    try:
        client.close()       # ← NameError if accept() failed
    except Exception:
        pass
    server.close()
```

If `server.accept()` raises an exception (other than `KeyboardInterrupt`), `client` is never assigned. The `finally` block runs anyway and `client.close()` raises `NameError`. The inner `except Exception: pass` catches it, so the script doesn't crash — but the *original* exception from `accept()` propagates out, which is correct behavior. However, relying on a second exception to be silently caught is fragile.

**Fix:** Initialize `client = None` before the `try` block and guard the close:

```python
client = None
try:
    client, addr = server.accept()
    ...
finally:
    if client is not None:
        try:
            client.close()
        except Exception:
            pass
    server.close()
```

---

### #8 — Low: `stdin_fd` may be unbound if `os.open` fails

**File:** `spp_server.py` lines 86-106

```python
def stdin_to_bt():
    try:
        stdin_fd = os.open("/dev/stdin", os.O_RDONLY)
        while running.is_set():
            ...
    except Exception:
        pass
    finally:
        running.clear()
        try:
            os.close(stdin_fd)      # NameError if os.open raised
        except Exception:
            pass
```

Same pattern as #7. If `os.open("/dev/stdin")` fails (permissions, /dev not mounted), `stdin_fd` is never assigned, and `os.close()` in `finally` raises `NameError` which is silently caught. Harmless in practice because the inner `except Exception` swallows it, but sloppy.

**Severity is Low** because this code runs on a known Linux machine where `/dev/stdin` is always available, and the double-swallow doesn't crash anything — the thread just dies silently (which is already a problem covered by #1).

---

### #9 — Critical: `socket.read()` / `socket.write()` / `socket.flush()` do not exist

**Files:** `spp_client.py` lines 33, 48, 49; `spp_simple.py` lines 44, 60, 61

```python
# spp_client.py / spp_simple.py — bt_to_stdout thread:
data = rfcomm.read(1024)          # ← AttributeError: no 'read'

# spp_client.py / spp_simple.py — main thread:
rfcomm.write(data)                # ← AttributeError: no 'write'
rfcomm.flush()                    # ← AttributeError: no 'flush'
```

**Verified on Python 3.14.4:** `socket.socket` objects have **none** of these methods. Only `recv()` and `send()` / `sendall()` exist:

```
>>> s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
>>> hasattr(s, 'read')    # False
>>> hasattr(s, 'write')   # False
>>> hasattr(s, 'flush')   # False
>>> hasattr(s, 'recv')    # True
>>> hasattr(s, 'send')    # True
```

`spp_server.py` uses the correct `sock.recv()` / `sock.send()` API. `spp_client.py` and `spp_simple.py` use a non-existent file-like API that will raise `AttributeError` on the first call. The `bt_to_stdout` thread catches only `(OSError, ValueError)`, not `AttributeError`, so the exception propagates out of the thread (but it's a daemon, so the process doesn't crash — the thread simply dies silently and `running.clear()` is never called in `finally` because the exception happens before the finally block... wait, actually `finally` DOES run even on uncaught exceptions. So `running.clear()` runs, and the bridge exits cleanly, just without ever having read or written any data).

**Fix:** Use `rfcomm.recv(1024)` and `rfcomm.sendall(data)` (or `rfcomm.send(data)`), matching the pattern in `spp_server.py`. Remove the `rfcomm.flush()` call entirely — it's a no-op concept on TCP/RFCOMM sockets.

---

### #10 — Medium: Zero error handling in setup script

**File:** `setup_bt.py` (entire file)

```python
adapter.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
```

No `try`/`except` anywhere. If BlueZ is not running, the D-Bus service is unavailable, or the adapter is missing, the script crashes with an unhelpful traceback:

```
dbus.exceptions.DBusException: org.freedesktop.DBus.Error.ServiceUnknown
```

This is a setup script that a user runs manually — a friendly error message is more important here than in automated code.

**Fix:** Wrap in `try`/`except` with human-readable messages:

```python
try:
    adapter.Set(...)
except dbus.DBusException as e:
    sys.exit(f"❌ BlueZ error: {e}\n   Is bluetoothd running?")
```

---

### #11 — Low: PEP 8 — comma-separated imports

**Files:** `spp_server.py` line 14, `spp_client.py` line 14, `spp_simple.py` line 14

```python
import os, sys, socket, threading      # PEP 8 violation
```

[PEP 8](https://peps.python.org/pep-0008/#imports) says: "Imports should usually be on separate lines."

**Fix:**

```python
import os
import sys
import socket
import threading
```

Note: `setup_bt.py` already follows this convention correctly.

---

### #12 — Low: Magic numbers throughout

**All files.**

| Value | Location | Meaning |
|-------|----------|---------|
| `4096` | spp_server.py:74 | RFCOMM recv buffer |
| `4096` | spp_server.py:95 | stdin read buffer |
| `4096` | spp_client.py:52 | stdin read buffer |
| `1024` | spp_client.py:33 | RFCOMM read buffer (inconsistent with 4096!) |
| `1024` | spp_simple.py:44 | RFCOMM read buffer |
| `0.5` | multiple | select timeout / join timeout |
| `1` | multiple | join timeout, sleep |
| `4` | all files | RFCOMM channel |

The RFCOMM channel `4` is duplicated across all files as both a module-level constant (good) and via `os.environ.get("SPP_CHANNEL", "4")` (inconsistent). The buffer size `1024` vs `4096` inconsistency is especially suspicious — why 1KB in the `select`-based bridges but 4KB in the thread-based bridge?

**Fix:** Define named constants:

```python
BUFFER_SIZE = 4096
SELECT_TIMEOUT = 0.5
JOIN_TIMEOUT = 1.0
```

---

### #13 — Low: `import time` inside except block

**File:** `spp_server.py` lines 135-138

```python
except Exception as e:
    print(f"⚠️  Erro: {e}", flush=True)
    import time           # ← lazy import in error path
    time.sleep(1)
```

Imports inside except blocks are unusual and can mask `ImportError` (if `time` fails to import for some reason, the original exception is lost). The `time` module is already standard and trivial to import at the top.

**Fix:** Move `import time` to the top of the file.

---

### #14 — Low: Missing `if __name__ == "__main__"` guard

**File:** `setup_bt.py`

The file has no guard — all D-Bus calls execute at import time. If someone accidentally does `import setup_bt`, the Bluetooth adapter is immediately reconfigured. This is a harmless footgun for a setup script, but still a Python best-practice violation.

**Fix:** Wrap the body in `if __name__ == "__main__":`.

---

### #15 — High: Non-existent socket I/O API in client + simple (cross-reference to #9)

**Cross-file.**

| File | BT read | BT write | stdin read | Architecture |
|------|---------|----------|------------|--------------|
| spp_server.py | `sock.recv(4096)` ✅ | `sock.send(data)` ✅ | `os.read(fd, 4096)` | 2 threads, raw fd |
| spp_client.py | `rfcomm.read(1024)` ❌ | `rfcomm.write()`+`flush()` ❌ | `sys.stdin.buffer.read(4096)` | 1 thread + main, select |
| spp_simple.py | `rfcomm.read(1024)` ❌ | `rfcomm.write()`+`flush()` ❌ | `sys.stdin.buffer.read(4096)` | 1 thread + main, select |

`spp_server.py` uses the correct `socket.recv()` / `socket.send()` API. `spp_client.py` and `spp_simple.py` call `rfcomm.read()`, `rfcomm.write()`, and `rfcomm.flush()` — methods that **definitively do not exist** on Python 3.14 `socket.socket` objects (verified via `hasattr`). This is the same issue as #9 but contextualized as a cross-file consistency problem: the server got it right, the client and simple files got it wrong, likely due to copy-pasting from a non-socket file-like API example.

Additionally, even once corrected, the three files will still use different I/O strategies. The `os.read()` approach in `spp_server.py` is justified by the docstring (Python 3.14 threading issue with `sys.stdin.buffer.read()` in background threads). The correct API is `recv()`/`send()` for sockets, and either `os.read()` or `sys.stdin.buffer.read()` for stdin depending on threading context.

---

## Architecture Note: The Three-File Problem

The project has three files that all serve the same purpose (Bluetooth SPP bridge):

| File | Role | Special features |
|------|------|-----------------|
| `spp_server.py` | SPP server (T470 listens) | BlueZ SDP registration, multi-connection loop, `os.read()` |
| `spp_simple.py` | SPP server (T470 listens) | Raw RFCOMM only, no SDP, single connection |
| `spp_client.py` | SPP client (T470 connects to Android) | No SDP needed, connects outward |

`spp_simple.py` is a strict subset of `spp_server.py` (server minus SDP). `spp_client.py` reuses the bridge logic but reverses the direction. A better architecture would be:

```
spp_common.py    — bridge(), constants, shared utilities
spp_server.py    — SDP + accept loop (imports spp_common)
spp_client.py    — connect + bridge (imports spp_common)
```

`spp_simple.py` could be removed entirely — running `spp_server.py` without the SDP registration (or with a `--no-sdp` flag) achieves the same thing.

---

## Verdict

The code works but has significant hygiene issues. The most urgent fixes:

1. **Critical — #9:** `spp_client.py` and `spp_simple.py` call `rfcomm.read()`, `rfcomm.write()`, and `rfcomm.flush()` — methods that **do not exist** on Python 3.14 `socket.socket` objects. These files cannot execute. Replace with `recv()` / `sendall()`.
2. **Critical — #1/#2:** Replace bare `except: pass` with proper exception handling and logging. Silent thread death is the hardest class of bug to diagnose.
3. **High — #3:** Extract the duplicated `bridge()` into a shared module before the two copies diverge (and so the API fix from #9 only needs to be applied once).
4. **High — #5:** Add a stdout mutex to prevent garbled terminal output.

The remaining issues are code-quality improvements that would make the codebase more maintainable and robust.
