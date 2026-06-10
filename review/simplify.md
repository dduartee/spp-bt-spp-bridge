# 🔍 Simplification Review — spp-t470

> Reviewed: `spp_server.py`, `spp_client.py`, `spp_simple.py`, `setup_bt.py`, `README.md`  
> Scope: unnecessary complexity, redundancy, dead code. Not logic review.

---

## 1. Duplicate `bridge()` — 3 files, 2 distinct implementations

### The problem

The `bridge()` function appears in all three `.py` files — but only **two distinct implementations** exist, and one of them is copy-pasted verbatim:

| File | bridge() implementation | lines |
|------|------------------------|-------|
| `spp_server.py` | `os.read("/dev/stdin")` + `sock.recv()`/`sock.send()` + `threading.Event` | 54 |
| `spp_client.py`  | `select.select()` + `rfcomm.read()`/`rfcomm.write()` | 44 |
| `spp_simple.py`  | **identical copy** of `spp_client.py` version | 44 |

**`spp_client.py` and `spp_simple.py` share the exact same `bridge()` function — character-for-character identical.** Any bug fix or improvement needs to be applied twice.

Additionally, the two implementations use different socket I/O patterns:
- `spp_server.py`: `sock.recv()` / `sock.send()` — correct raw socket API
- `spp_client.py` + `spp_simple.py`: `rfcomm.read()` / `rfcomm.write()` — file-like API that is **not part of `socket.socket`**; these would need `sock.makefile()` to work

### Recommendation

**Extract a single canonical `bridge()` into a shared module** (`bt_bridge.py` or `spp_common.py`), then import it from all scripts. Choose the `recv()`/`send()` approach from `spp_server.py` — it's the documented Python socket API and doesn't depend on `makefile()` wrapping.

```python
# New file: spp_common.py
def bridge(sock, label=""): ...
```

Then in `spp_server.py`, `spp_client.py`, `spp_simple.py`:
```python
from spp_common import bridge
```

**Estimated savings:** ~90 lines of duplicated code removed, 1 source of truth.

---

## 2. `spp_simple.py` is a strict subset of `spp_server.py`

### The problem

`spp_simple.py` (93 lines) offers "server mode without D-Bus SDP." It differs from `spp_server.py` (121 lines) only by removing:

| Feature | spp_server.py | spp_simple.py |
|---------|:---:|:---:|
| Raw RFCOMM socket | ✅ | ✅ (identical) |
| D-Bus SDP registration | ✅ | ❌ |
| GLib mainloop thread | ✅ | ❌ |
| Multi-connection loop | ✅ | ❌ (single accept) |
| `bridge()` function | own impl | own impl |

The code is ~75% overlap. The README already documents `spp_server.py` as the primary entry point — `spp_simple.py` exists only as a fallback for when SDP registration fails.

### Recommendation

**Merge `spp_simple.py` into `spp_server.py`** with a `--no-sdp` flag. This eliminates an entire file while preserving both use cases:

```python
# spp_server.py
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-sdp", action="store_true", help="Skip D-Bus SDP registration")
    args = parser.parse_args()
    # ... if not args.no_sdp: register SDP ...
```

The single-connection vs multi-connection loop difference can also be gated by a flag (`--once`), or the simpler single-connection behavior can become the default since the multi-connection loop has marginal value for this proof-of-concept (the server sits idle between connections waiting for the same Android device anyway).

**Estimated savings:** ~90 lines removed (whole file), 1 less script to maintain.

---

## 3. `setup_bt.py` — one-shot utility, could be a subcommand

### The problem

`setup_bt.py` (33 lines) sets Bluetooth adapter properties (Powered, Discoverable, Pairable, DiscoverableTimeout). It runs once and is never needed again. The README says `python3 setup_bt.py # garantir discoverable (1x)`.

### Recommendation

**Option A (Keep separate):** `setup_bt.py` is small, self-contained, and only needed once. Keeping it separate is fine.

**Option B (Integrate):** If consolidating into one script (see finding #4), add a `--setup` subcommand:

```python
# spp.py setup
```

Both are reasonable. No strong recommendation — this isn't a real complexity problem.

**Minor nit:** The script queries all adapter properties with `GetAll()` just to print them. If the user only needs to verify that `Discoverable` took effect, query only that property with `Get()` instead:

```python
# Before
props = adapter.GetAll("org.bluez.Adapter1")

# After — just what we need
name = adapter.Get("org.bluez.Adapter1", "Name")
addr = adapter.Get("org.bluez.Adapter1", "Address")
disc = adapter.Get("org.bluez.Adapter1", "Discoverable")
```

This avoids fetching ~20 unused properties from the D-Bus object.

---

## 4. Consolidation target: 4 scripts → 1 or 2

### The problem

The 4 Python scripts total ~340 lines but share:
- Bluetooth socket creation boilerplate
- The `bridge()` function (in two variants)
- D-Bus connection setup
- The same adapter MAC address and channel

A new contributor needs to understand which script to use for which scenario.

### Recommendation: 2 scripts

| Script | Purpose | Replaces |
|--------|---------|----------|
| `spp.py` | Main entry: `server`, `client`, `setup` subcommands | `spp_server.py`, `spp_simple.py`, `spp_client.py`, `setup_bt.py` |
| `spp_common.py` | Shared: `bridge()`, adapter config, SDP registration helpers | (new) |

**Single-file alternative:** Everything in one `spp.py` with subcommands. Feasible at ~250 lines total. The tradeoff is that `setup_bt.py` is an admin utility — it may be cleaner to keep it as a separate `--setup` flag rather than a standalone script, since it requires root-adjacent D-Bus permissions that the bridge itself doesn't.

Either consolidation cuts the mental model from "4 scripts with overlapping concerns" to "1 command with clear modes."

---

## 5. Over-engineering: multi-connection loop in `spp_server.py`

### The problem

`spp_server.py` implements a `while True` loop that accepts connections, runs the bridge, then re-accepts after disconnect:

```python
while True:
    client, addr = server.accept()
    conn_count += 1
    bridge(client, f" (#{conn_count})")
    print("Re-aguardando...")
```

For this proof-of-concept, there is exactly one expected client (the S23 Android phone). The reconnection loop adds:
- A connection counter (`conn_count`)
- An `except Exception` catch-all with `time.sleep(1)` retry
- State management around the `KeyboardInterrupt` propagation

None of this is wrong, but it adds complexity for a scenario (multiple/sequential clients) that the README never describes.

### Recommendation

Simplify to single-accept unless multi-client is a real need:

```python
client, addr = server.accept()
print(f"✅ Conectado: {addr}", flush=True)
bridge(client)
```

If reconnect-on-disconnect is genuinely useful (dropped connections happen), keep the loop but drop the connection counter and the `" (#{conn_count})"` label — it's debug noise that the user never acts on.

---

## 6. D-Bus SDP setup: can it be simpler?

### The problem

The SDP registration in `spp_server.py` (lines 44–77) is ~34 lines:

```python
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
```

This is close to the minimum required by BlueZ 5's `ProfileManager1` API. The XML `SERVICE_RECORD` is verbose but BlueZ requires it — no simplification possible there without an external SDP library (which would add a dependency, defeating the purpose).

### What can be simplified

- **`"RequireAuthentication": False` and `"RequireAuthorization": False`** are both defaults in BlueZ. They can be omitted unless the project needs to be explicit about security posture for documentation.
- **`PROFILE_PATH`** (`"/bluetooth/profile/spp_t470"`) is arbitrary — it could be inlined into the `RegisterProfile` call. But extracting it as a constant is the right call for readability.
- **The GLib mainloop thread** is unavoidable if using `ProfileManager1` — BlueZ requires a running GLib event loop to process D-Bus method returns. This is documented in the BlueZ API and can't be simplified away.

### Verdict

The D-Bus SDP setup is already close to minimal. **No meaningful simplification possible** beyond omitting the two default `Require*` options.

---

## 7. Minor issues

### 7a. `import time` inside exception handler (spp_server.py line 107)

```python
except Exception as e:
    print(f"⚠️  Erro: {e}", flush=True)
    import time          # ← lazy import inside except block
    time.sleep(1)
```

**Fix:** Move `import time` to the top of the file. There's no circular import issue or startup perf concern — this is purely stylistic inconsistency.

### 7b. Verbose error message in spp_client.py (lines 79–85)

Seven separate `print()` calls for what is logically one error message block:

```python
print(f"❌ Erro ao conectar: {e}", flush=True)
print(f"   Verifique se o BT SPP Bridge está rodando no S23", flush=True)
print(f"   MAC do S23: {s23_mac}", flush=True)
print(f"   Canal: {channel}", flush=True)
print(f"", flush=True)
print(f"   Para configurar MAC diferente:", flush=True)
print(f"   S23_MAC=XX:XX:XX:XX:XX:XX python3 spp_client.py", flush=True)
```

**Fix:** Use a single multi-line string:

```python
print(f"""❌ Erro ao conectar: {e}
   Verifique se o BT SPP Bridge está rodando no S23
   MAC do S23: {s23_mac}
   Canal: {channel}

   Para configurar MAC diferente:
   S23_MAC=XX:XX:XX:XX:XX:XX python3 spp_client.py""", flush=True)
```

### 7c. `spp_client.py` imports `os` but not `select` (it's used)

Actually — `spp_client.py` imports `os` at the top (used in `main()` for `os.environ.get`) and `select` (used in `bridge()`). All imports are used. No dead imports.

### 7d. `spp_simple.py` omits `os` from bridge but imports it

`spp_simple.py` imports `os` at the top but the bridge function doesn't use `os` (unlike `spp_server.py` which uses `os.read`/`os.open`/`os.close`). However, `spp_simple.py`'s bridge doesn't reference `os` at all. This is a dead import inherited from the copy-paste.

### 7e. `BrokenPipeError` vs `BrokenPipeError` inconsistency

`spp_server.py` catches `BrokenPipeError` (correct). `spp_client.py` catches `BrokenPipeError` at the top-level `except` in `main()` — but `BrokenPipeError` is a subclass of `OSError` in Python 3.3+, so the separate catch in `spp_client.py`'s main() is redundant with the `except (OSError, BrokenPipeError)` already present. Not a simplification issue per se, but a consistency note.

---

## 8. Summary of recommendations

| # | Recommendation | Impact | Effort |
|---|---------------|--------|--------|
| 1 | Extract `bridge()` to shared `spp_common.py` | Lowers duplication, single source of truth | Medium |
| 2 | Merge `spp_simple.py` into `spp_server.py` with `--no-sdp` | Eliminates a file, preserves functionality | Medium |
| 3 | Keep `setup_bt.py` separate OR make it `spp.py setup` | Either is fine | Low |
| 4 | Target 1–2 scripts total instead of 4 | Simpler mental model | Medium |
| 5 | Simplify multi-connection loop (drop counter + label) | Less code, same behavior | Low |
| 6 | D-Bus SDP: already minimal, drop optional `Require*` opts | Marginal | Low |
| 7a | Move `import time` to top of `spp_server.py` | Consistency | Trivial |
| 7b | Collapse 7 `print()` calls into 1 in `spp_client.py` | Readability | Trivial |
| 7d | Remove unused `import os` from `spp_simple.py` | Cleanliness | Trivial |

### Recommended order of execution

1. **First:** Extract shared `bridge()` + config constants to `spp_common.py` (finding #1)
2. **Then:** Merge `spp_simple.py` → `spp_server.py` with `--no-sdp` (finding #2)
3. **Then:** Decide on `setup_bt.py` disposition (finding #3)
4. **Finally:** Apply minor fixes (findings #7a, #7b, #7d)

### What NOT to change

- The D-Bus SDP XML record — it's verbose but BlueZ-mandated
- The GLib mainloop thread in `spp_server.py` — required by `ProfileManager1`
- The `os.read("/dev/stdin")` approach in `spp_server.py`'s bridge — documented workaround for Python 3.14 threading issue
- `setup_bt.py`'s `DiscoverableTimeout=0` — correct and necessary for the use case
- The `socket.AF_BLUETOOTH` / `BTPROTO_RFCOMM` raw socket approach — this is the simplest path given BlueZ 5.86 limitations
