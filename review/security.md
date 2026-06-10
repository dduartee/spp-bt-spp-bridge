# Security Audit: BT SPP Bridge (spp-t470)

**Date:** 2026-06-10  
**Scope:** Python scripts (`spp_server.py`, `spp_client.py`, `spp_simple.py`, `setup_bt.py`), Android code (`BridgeService.java`, `build.sh`), project structure  
**Methodology:** Manual code review against the Security and Hardening framework (Three-Tier Boundary System, OWASP Top 10)

---

## Risk Levels

| Symbol | Meaning |
|--------|---------|
| 🔴 **CRITICAL** | Immediate fix required — active exploit possible |
| 🟠 **HIGH** | Significant risk — fix in current sprint |
| 🟡 **MEDIUM** | Real risk — fix in next release cycle |
| 🟢 **LOW** | Best-practice gap — fix when convenient |
| ℹ️ **INFO** | Observation — no immediate action needed |

---

## Findings

### 1. 🔴 No Bluetooth Authentication or Encryption

**Files:** `spp_server.py` lines 120–121, `setup_bt.py` lines 21–25

The SPP server explicitly **disables all Bluetooth security**:

```python
# spp_server.py lines 120-121
"RequireAuthentication": False,
"RequireAuthorization": False,
```

Combined with `setup_bt.py` which sets the adapter to permanently discoverable with **no timeout**:

```python
adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
adapter.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
adapter.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))  # NEVER expires
```

**Impact:** Any Bluetooth device within ~10m range can:

- See the T470 permanently advertising as "t470"
- Connect to RFCOMM channel 4 **without pairing, PIN, or any authentication**
- Read all data the T470 sends to stdout
- Inject arbitrary data into the T470's stdin (which is bridged directly to whatever process is consuming the SPP output — potentially an AI agent or shell)

This is equivalent to an open, anonymous network socket with no access controls.

**Recommendation:** Set `RequireAuthentication: True` and `RequireAuthorization: True`. Use a non-zero `DiscoverableTimeout` (e.g., 120 seconds). Implement a pairing acceptance callback.

---

### 2. 🔴 Zero Input Validation on Bluetooth Data

**Files:** `spp_server.py` lines 70–75, `spp_client.py` lines 27–33, `spp_simple.py` lines 27–33

All three bridge implementations forward raw bytes from stdin to the Bluetooth socket and vice-versa with **zero validation, sanitization, or rate limiting**:

```python
# spp_server.py — bridge function
data = os.read(stdin_fd, 4096)    # read raw bytes from stdin
sock.send(data)                    # forward directly to Bluetooth — no checks

data = sock.recv(4096)             # receive raw bytes from Bluetooth
sys.stdout.buffer.write(data)      # forward directly to stdout — no checks
```

**Impact:**

- No size limits: an attacker could flood the connection with megabytes of data
- No content validation: binary data, control characters, ANSI escape sequences, terminal command injection all pass through unfiltered
- If stdout on the T470 side feeds into a shell or an AI agent that interprets commands, Bluetooth data becomes a remote code execution vector
- No rate limiting: trivial DoS by saturating the RFCOMM channel

**Recommendation:** Add maximum message size limits (e.g., 64KB per message). Sanitize or at minimum log incoming data. If the consuming process is an AI agent or shell, implement an allowlist of expected content patterns. Add rate limiting.

---

### 3. 🟠 Hardcoded MAC Addresses and Bluetooth Identifiers

**Files:** `spp_server.py` line 27, `spp_simple.py` line 28, `spp_client.py` line 79, `BridgeService.java` lines 27–30

| Identifier | Value | File |
|-----------|-------|------|
| T470 MAC | `F4:96:34:60:D6:3B` | `spp_server.py`, `spp_simple.py` |
| S23 MAC | `64:1B:2F:31:20:48` | `spp_client.py` |
| Custom UUID | `977c4a04-bf68-4c23-bf49-dac84b22d774` | `spp_server.py`, `BridgeService.java` |
| Standard SPP UUID | `00001101-0000-1000-8000-00805F9B34FB` | `BridgeService.java` |

**Impact:**

- Device fingerprints are embedded in source code — disclosure of hardware identities
- Makes the code non-portable (can only run on this specific T470)
- If this code is ever committed to a public repository, these identifiers are permanently exposed
- The S23 MAC as a **default** in `spp_client.py` (`os.environ.get("S23_MAC", "64:1B:2F:31:20:48")`) exposes a real device address even when the environment variable isn't set

**Recommendation:** Move all device identifiers to environment variables or a config file excluded from version control. Use `""` or `None` as defaults so the script fails rather than silently connecting to a hardcoded address.

---

### 4. 🟠 Android App: Unauthenticated TCP Bridge with Java Reflection

**Files:** `BridgeService.java` lines 31, 87–105, 130–134, `build.sh` lines 98–108

The Android app opens an **unauthenticated TCP server on port 8090** bound to all interfaces:

```java
// BridgeService.java
private static final int TCP_PORT = 8090;
tcpServer = new ServerSocket(TCP_PORT);  // binds to 0.0.0.0:8090
tcpServer.setReuseAddress(true);
```

Additionally, the app uses **Java reflection to bypass Android API restrictions**:

```java
// Bypasses createRfcommSocketToServiceRecord() failure by directly calling hidden API
Method m = device.getClass().getMethod("createRfcommSocket", int.class);
btSocket = (BluetoothSocket) m.invoke(device, channel);
```

And the build script **hardcodes the debug keystore password**:

```bash
# build.sh line 100
DEBUG_PASS="android"
```

**Impact:**

- **TCP port 8090:** Any app on the Android device (including malicious ones with `INTERNET` permission) can connect to `localhost:8090` and inject data into the Bluetooth stream or exfiltrate Bluetooth data
- **Reflection:** Relies on undocumented, unsupported Android internals that may change between OS versions; also bypasses any security checks Google may add to the official API
- **Hardcoded keystore password:** The `"android"` password is the standard Android debug keystore password — publicly known. If this build process is ever used for a release APK, the signing key is effectively public.

**Recommendation:** Bind TCP to `127.0.0.1` only (not `0.0.0.0`). Consider adding a simple shared secret or token for TCP clients. For the reflection fallback, add a comment warning that this is a PoC and should not be used in production. Never use the debug keystore for anything beyond local development.

---

### 5. 🟡 D-Bus Profile Registration Without Access Controls

**Files:** `spp_server.py` lines 108–127, `setup_bt.py` lines 13–15

Both scripts access the **system D-Bus** (`dbus.SystemBus()`) and modify Bluetooth adapter state without any application-level authentication:

```python
# setup_bt.py — directly modifies adapter properties
bus = dbus.SystemBus()
adapter = dbus.Interface(bus.get_object("org.bluez", "/org/bluez/hci0"), ...)
adapter.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))

# spp_server.py — registers SDP profile
manager.RegisterProfile(PROFILE_PATH, SPP_UUID, opts)
```

**Impact:**

- Relies entirely on OS-level D-Bus policy (typically: only `root` and users in the `bluetooth` group can access `org.bluez`)
- If D-Bus policy is misconfigured or the script runs as root, any process could register Bluetooth profiles
- No validation that the caller actually owns the Bluetooth adapter they're configuring
- The `RegisterProfile` call with `RequireAuthentication: False` permanently weakens the Bluetooth security posture

**Recommendation:** At minimum, verify the script runs with appropriate user permissions before modifying adapter state. Document the D-Bus policy dependency. The real fix is enabling `RequireAuthentication` (see Finding #1).

---

### 6. 🟡 No Encryption for Data in Transit (Application Layer)

**Files:** `spp_server.py`, `spp_client.py`, `spp_simple.py`, `BridgeService.java`

All bridge implementations transmit data as **raw, unencrypted bytes** over:

- Bluetooth RFCOMM (link-layer encryption depends on pairing — which is disabled)
- TCP on port 8090 (no TLS, no encryption at all)

```
T470 stdin → [raw bytes] → Bluetooth RFCOMM (unencrypted) → S23 app → TCP :8090 (plaintext) → nc/Termux
```

**Impact:**

- RFCOMM link-layer encryption is disabled (`RequireAuthentication: False`) — Bluetooth data is transmitted in cleartext
- TCP bridge on the Android side has no TLS — any process on the device can sniff localhost traffic
- If this bridge were ever extended to use non-localhost TCP, it would be trivially interceptable

**Recommendation:** Enable Bluetooth authentication to activate link-layer encryption (see Finding #1). For the TCP bridge on Android, at minimum bind to `127.0.0.1`. If the bridge is extended beyond localhost, add TLS.

---

### 7. 🟡 SSH Connection Uses Password Authentication

**File:** `bt-spp-bridge/app/PLANO.md` lines 428–439

The project architecture relies on SSH from T470 to S23, but uses **password authentication with no key-based auth**:

```
sshd rodando na porta 8022
authorized_keys vazio (usa senha)
SSH: T470 conectado ao S23 via `ssh u0_a471@10.0.0.35 -p 8022`
```

**Impact:**

- Password authentication is susceptible to brute-force attacks
- No key-based authentication means the connection can't be automated securely
- If the password is ever stored in a script or environment variable, it becomes a credential leak risk

**Recommendation:** Generate an SSH key pair on the T470, add the public key to S23's `authorized_keys`, and disable password authentication for this connection.

---

### 8. 🟢 World-Executable Python Scripts

**Files:** All `.py` files (mode `755` / `rwxr-xr-x`)

```bash
-rwxr-xr-x  spp_server.py
-rwxr-xr-x  spp_client.py
-rwxr-xr-x  spp_simple.py
-rwxr-xr-x  setup_bt.py
```

**Impact (low):** World-executable permissions mean any user on the system can run these scripts. Since they don't contain secrets (the MAC addresses are already in the code), and Bluetooth access is gated by D-Bus group membership, this is a minor concern on a single-user laptop.

**Recommendation:** Change to `755` is already reasonable for scripts. For defense-in-depth, consider `750` (owner + group only) if other users exist on the system.

---

### 9. ℹ️ No `eval()`/`exec()`/`subprocess` Usage

**Files:** All `.py` files

**Result: CLEAN.** No dangerous dynamic execution functions were found in any Python file. The code uses safe, standard library APIs (`socket`, `os.read`, `threading`, `dbus`).

---

### 10. ℹ️ No Secrets in Source Code

**Result: CLEAN.** No API keys, passwords, tokens, private keys, certificates (`.pem`, `.crt`, `.key`), or `.env` files were found in the project directory. The only password-like value is the debug keystore password `"android"` in `build.sh`, which is the publicly documented Android debug default.

---

### 11. ℹ️ No Git Repository — No Commit History Risk

**Result: CLEAN.** No `.git` directory exists. There is no risk of accidentally committed secrets in version control history.

---

## Summary Matrix

| # | Finding | Risk | File(s) | Effort to Fix |
|---|---------|------|---------|---------------|
| 1 | No Bluetooth auth/encryption | 🔴 CRITICAL | `spp_server.py:120-121`, `setup_bt.py:21-25` | Low (2-line change) |
| 2 | Zero input validation | 🔴 CRITICAL | `spp_server.py:70-75`, `spp_client.py`, `spp_simple.py` | Medium |
| 3 | Hardcoded MAC addresses | 🟠 HIGH | `spp_server.py:27`, `spp_client.py:79`, `spp_simple.py:28` | Low |
| 4 | Unauthenticated TCP + reflection | 🟠 HIGH | `BridgeService.java`, `build.sh:100` | Medium |
| 5 | D-Bus without access controls | 🟡 MEDIUM | `spp_server.py`, `setup_bt.py` | Low (documentation) |
| 6 | No app-layer encryption | 🟡 MEDIUM | All Python + Java files | Medium |
| 7 | SSH password auth | 🟡 MEDIUM | Architecture (PLANO.md) | Low |
| 8 | World-executable scripts | 🟢 LOW | All `.py` files | Low |
| 9 | No eval/exec/subprocess | ℹ️ CLEAN | All `.py` files | N/A |
| 10 | No secrets in code | ℹ️ CLEAN | All files | N/A |
| 11 | No git repo | ℹ️ CLEAN | Project root | N/A |

---

## Priority Fix Plan

### Immediate (Critical)

1. **Enable Bluetooth authentication and authorization** — Change `RequireAuthentication` and `RequireAuthorization` to `True` in `spp_server.py` line 120-121. Set a non-zero `DiscoverableTimeout` in `setup_bt.py`.

2. **Add input validation** — Implement a maximum message size (e.g., 64KB) in all bridge functions. Add content-type validation if the consuming process has specific expectations. Log unexpected data patterns.

### Short-term (High)

3. **Externalize device identifiers** — Move MAC addresses and UUIDs to environment variables or a config file.
4. **Bind TCP to localhost only** — Change `ServerSocket(TCP_PORT)` to bind `127.0.0.1` explicitly in `BridgeService.java`.
5. **Switch SSH to key-based auth** — Generate key pair, populate `authorized_keys` on S23.

### Medium-term (Medium)

6. **Document D-Bus dependency** — Add comments noting the Bluetooth group requirement.
7. **Audit bridge data path** — Trace exactly what consumes the stdout data on the T470 side. If it's an AI agent or shell, implement content filtering.

---

## Notes

- This is a **proof-of-concept** project built rapidly by AI agents. The security posture reflects prototype-level priorities (functionality first).
- The most critical finding (#1) is a **conscious design choice** documented in the code — the developers explicitly set `RequireAuthentication: False` for ease of testing. This must be reversed before any non-isolated use.
- The project does **not** currently have a git repository, which is a positive finding — no risk of leaked secrets in history.
- No SSH private keys, certificates, or sensitive credential files were found anywhere in the project directory.
