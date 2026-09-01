# BMCU 370C DM PRO Firmware for Bambu Lab A1

This repository is a focused firmware fork for the **BMCU 370C DM PRO dual-microswitch hardware** used with the **Bambu Lab A1**.

It keeps the original BMCU hardware and firmware foundation, but the current codebase has been substantially simplified and extended around the DM PRO hardware, A1 operation, dual-microswitch filament handling, AS5600 feedback, deterministic unloading, and a more complete Bambu AMS bus identity/registration layer.

## Attribution

This project is based on the original **BMCU-C-PJARCZAK** work by **Paweł Jarczak / `jarczakpawel`**.

Original upstream repository:

https://github.com/jarczakpawel/BMCU-C-PJARCZAK

The original project provided the BMCU hardware support, bus implementation, motion-control foundation, calibration, filament state handling, persistence, and the community work that made BMCU possible. The work in this fork builds on that foundation rather than replacing or claiming authorship of it.

If you are looking for the broader upstream BMCU project, other printer families, other PCB variants, or the original general-purpose firmware documentation, use the upstream repository above.

---

## Scope of this fork

This repository targets:

- **BMCU 370C DM PRO**
- **dual filament microswitches**
- **AS5600 magnetic encoder / buffer sensing**
- **Bambu Lab A1**
- Bambu AMS-style bus communication

This is intentionally not the general-purpose upstream firmware matrix. Legacy instructions for single-switch boards, alternate loading modes, unrelated printer families, old firmware generations, and obsolete flashing/build combinations have been removed from this README.

---

## Main features

### DM PRO dual-microswitch operation

The firmware treats the two physical filament switches separately.

- **Rear / spool-side microswitch**
  - used as the automatic filament-load trigger
- **Front / output / toolhead-side microswitch**
  - used as the normal unload completion sensor

The current decoded switch states are:

| State | Meaning |
|---:|---|
| `0` | neither switch active |
| `1` | both switches active |
| `2` | rear / spool-side switch only |
| `3` | front / output-side switch only |

This distinction is important. The rear switch is not used as the normal unload endpoint.

### Automatic filament loading

Normal DM PRO loading is:

```text
insert filament from spool side
        ↓
rear microswitch activates
        ↓
automatic feed starts
        ↓
filament reaches the front/output side
        ↓
loading completes
```

The existing buffer, pressure-control, AS5600, and anti-snag logic remains part of the loading system.

### Front-switch-terminated unloading

Normal commanded unload is sensor-driven rather than distance-driven.

```text
printer commands unload / pullback
        ↓
BMCU retracts filament
        ↓
front/output microswitch changes present → absent
        ↓
50 ms debounce
        ↓
motor stops
        ↓
unloaded / idle
```

A successful front-switch clear goes directly to the unloaded idle state. It does **not** enter the old redetect path and does not intentionally drive the filament again after a confirmed unload.

### Configurable maximum retract distance

Firmware builds are provided with selectable retract limits.

The configured distance is a **maximum / fallback distance**, not the normal unload distance.

For example:

```text
..._010  = maximum retract 100 mm
..._050  = maximum retract 500 mm
..._090  = maximum retract 900 mm
```

If the front/output microswitch clears before the configured maximum, the motor stops at the switch-clear event.

If the front switch never clears, the configured build length acts as the `MAX_DISTANCE` safety limit.

Available limits:

```text
010  100 mm
020  200 mm
025  250 mm
030  300 mm
035  350 mm
040  400 mm
045  450 mm
050  500 mm
055  550 mm
060  600 mm
065  650 mm
070  700 mm
075  750 mm
080  800 mm
085  850 mm
090  900 mm
```

### Pullback safety

Normal unload completion:

- `FRONT_SWITCH_CLEARED`

Safety termination conditions include:

- `MAX_DISTANCE`
- `TIMEOUT`
- `ENCODER_FAULT`

The former hidden jam-path behaviour that forced a fixed 100 mm retract and disabled the front-switch endpoint has been removed.

AS5600 health is monitored during motion so an encoder failure cannot allow an uncontrolled retract to continue indefinitely.

---

# Bambu AMS protocol support

The firmware contains a substantially expanded BambuBus implementation and now separates **physical device identity** from the **logical AMS ID assigned on the bus**.

## Stable physical identity

Each BMCU builds a stable serial/hardware identity from the CH32 MCU unique ID.

That means:

```text
same physical BMCU
        ↓
reboot / firmware restart
        ↓
same physical serial identity
```

The permanent device identity is kept separate from the current logical AMS slot.

## Dynamic AMS ID

Dynamic AMS identity is enabled by default.

The protocol state supports logical AMS IDs:

```text
0 = AMS A
1 = AMS B
2 = AMS C
3 = AMS D
```

and uses:

```text
0xFF = unassigned
```

The runtime state machine includes:

```text
UNASSIGNED
ASSIGNED
REGISTERING
ONLINE
LOST_HOST
```

The current assigned ID is used by motion, status, filament, version, serial, and MC-online protocol handlers rather than blindly answering as a compile-time slot.

## ID assignment and persistence

When dynamic-ID operation is enabled, the assigned AMS bus ID is stored in the existing flash/NVM system.

On reboot:

```text
valid stored ID
        ↓
restore ID
        ↓
registration starts again as a transient state
```

The registration state itself is not persisted.

This is deliberate: the device remembers its logical assignment, but still performs the current online/registration handshake with the printer after restart.

A dedicated persistent ID-clear path is also present in the identity subsystem. Development builds can force the stored assignment to be cleared on boot with `BMCU_CLEAR_ASSIGNED_ID_ON_BOOT` when required for enumeration testing.

## Online detection and registration

The existing Bambu online-detect exchange has been integrated into the runtime identity layer.

The device can participate in discovery/registration, accept a valid AMS ID in the online-detect exchange, rebuild its protocol-visible identity using that ID, and complete registration without relying solely on a compile-time `BAMBU_BUS_AMS_NUM` value.

The registration exchange retains the observed `0x0C` / `0x0A` online-detect phases used by the existing protocol implementation.

## Hot plug and automatic re-registration

The firmware now supports **protocol-level hot plug, reconnect, and host-restart recovery**.

Important behaviours include:

- a BMCU can join the bus while the printer is already running and participate in the normal online-detect/registration process
- loss of printer heartbeat clears the transient registration state
- the persisted AMS ID is retained across host loss
- when the printer returns, the BMCU can register again without requiring a BMCU power cycle
- a printer reboot while the BMCU remains powered is handled as host loss followed by re-registration
- disconnect/reconnect no longer requires the firmware to remain stuck in an old registered state

Conceptually:

```text
ONLINE
   ↓ heartbeat lost
LOST_HOST
   ↓ printer returns / discovery resumes
REGISTERING
   ↓ registration succeeds
ONLINE
```

The persistent logical ID is not erased simply because the printer disappears temporarily.

This hot-plug support is a **firmware/protocol capability**. As with any exposed powered bus, users are still responsible for correct hardware wiring and avoiding shorts or connector misalignment.

## Firmware and model identity

Firmware identity is centralized in:

```text
src/firmware_identity.h
```

The current protocol identity uses:

```text
model: AMS08
version bytes: 00 00 32 0A
```

The BambuBus implementation responds to the established long-frame version query rather than maintaining disconnected version bytes in multiple handlers.

## Implemented protocol handling

The current code recognizes and/or implements the following established traffic:

| Packet / type | Purpose |
|---|---|
| short `0x03` | filament motion command |
| short `0x04` | AMS status / motion exchange |
| short `0x05` | online detect / registration |
| short `0x08` | filament metadata update |
| short `0x20` | heartbeat |
| long `0x0103` | firmware/model version query |
| long `0x0211` | filament information read |
| long `0x0218` | filament information update |
| long `0x021A` | MC-online query |
| long `0x0402` | serial-number / identity query |
| long `0x040D` | certification frame recognition / observation |
| long `0x040E` | authorization frame recognition / observation |

CRC8/CRC16 validation, short/long frame parsing, package-number handling, request targeting, and response source/target swapping remain part of the bus layer.

### Certification and authorization frames

`0x040D` and `0x040E` are recognized so they can be observed and diagnosed, but this repository does **not** claim to possess or reproduce Bambu Lab private credentials, device certificates, or private signing keys.

Recognition of those frames is separate from ordinary AMS protocol compatibility.

---

# Protocol tracing

For protocol development, the firmware contains an optional trace mode:

```cpp
BMCU_BAMBU_PROTOCOL_TRACE=1
```

It is disabled by default.

When enabled it can report events such as:

```text
BBUS RX SHORT ...
BBUS RX LONG ...
BBUS TX LONG ...
ID ASSIGNED ...
ID CLEAR ...
REGISTER START ...
REGISTER OK ...
```

Unknown packets are rate-limited in the debug output so new protocol traffic can be investigated without flooding logs with heartbeat frames.

---

# Firmware builds

The repository currently keeps the following release/build families:

```text
AMS A
AMS B
AMS C
AMS D
SOLO
LITE
```

Each is generated for all 16 maximum retract limits listed above.

This produces the current 96-build release matrix:

```text
6 roles × 16 retract limits = 96 firmware binaries
```

Example environment names:

```text
dm_pro_ams_a_010
dm_pro_ams_a_050
dm_pro_ams_b_050
dm_pro_ams_c_090
dm_pro_ams_d_050
dm_pro_solo_050
dm_pro_lite_050
```

Example release binary names:

```text
BMCU-DM-PRO-AMS-A-010.bin
BMCU-DM-PRO-AMS-A-050.bin
BMCU-DM-PRO-AMS-B-050.bin
BMCU-DM-PRO-SOLO-090.bin
```

Dynamic AMS identity is enabled in the firmware protocol layer. The A/B/C/D build families are currently retained for compatibility, testing, and release organization rather than being the sole source of runtime AMS identity.

SOLO and LITE builds are retained as dedicated build families. Where they do not yet contain a distinct protocol implementation, the repository does not claim behaviour that is not present in the source.

---

# Releases and generated artifacts

GitHub Actions builds and packages the firmware matrix.

Release/package output includes:

- all generated `.bin` files
- role-specific ZIP files
- complete all-firmware ZIP
- `manifest.json`
- `manifest.csv`
- SHA-256 checksums
- generated firmware documentation

Role packages include:

```text
BMCU-DM-PRO-AMS-A.zip
BMCU-DM-PRO-AMS-B.zip
BMCU-DM-PRO-AMS-C.zip
BMCU-DM-PRO-AMS-D.zip
BMCU-DM-PRO-SOLO.zip
BMCU-DM-PRO-LITE.zip
BMCU-DM-PRO-ALL.zip
```

The release manifest records the build environment, role, retract limit, binary size, SHA-256, Git commit, source ref, PlatformIO/Python versions, and the firmware's documented load/unload semantics.

Tagged `v*` builds are packaged as GitHub Releases. Normal branch and pull-request builds produce GitHub Actions artifacts without publishing a release.

---

# Building locally

This project uses PlatformIO with the CH32V platform.

Build a specific environment with:

```bash
pio run -e dm_pro_ams_a_050
```

Other examples:

```bash
pio run -e dm_pro_ams_a_010
pio run -e dm_pro_ams_b_050
pio run -e dm_pro_ams_d_090
pio run -e dm_pro_solo_050
pio run -e dm_pro_lite_050
```

The normal PlatformIO binary is created under:

```text
.pio/build/<environment>/firmware.bin
```

For normal use, the packaged GitHub Actions / Release artifacts are easier to identify because they include consistent filenames, manifests, and checksums.

---

# Choosing a retract-limit build

Choose a limit that is comfortably longer than the physical distance required for the filament to clear the front/output microswitch during unload.

For example, if the front switch normally clears after approximately 120 mm of retract, a 100 mm maximum build cannot reach the normal front-switch completion condition. A 200 mm or larger maximum gives the sensor-driven unload enough room to complete normally.

The best test build when validating a new physical arrangement is usually one with a deliberately generous limit, for example `_050`, then confirm through observation or protocol/debug logging that unload stops on:

```text
FRONT_SWITCH_CLEARED
```

rather than:

```text
MAX_DISTANCE
```

The configured maximum exists as a safety fallback, not as a requirement to retract that entire distance.

---

# Calibration and persistent settings

The firmware continues to use the existing BMCU flash/NVM layer for calibration, filament metadata, loaded-channel state, and AMS bus-ID persistence.

Do not erase or reset calibration merely to change the assigned AMS bus ID. Bus assignment and physical calibration are separate pieces of state.

The ID-clear path is intended to clear logical bus assignment only; it is not intended to erase filament data, DM calibration, or the hardware-derived permanent serial identity.

---

# Current design summary

```text
LOAD

filament inserted from spool side
→ rear microswitch activates
→ automatic feed
→ front/output side reached
→ loaded


PRINT

AS5600 + buffer/pressure control remain active


UNLOAD

printer commands pullback
→ feeder retracts
→ rear switch may change
→ rear switch is ignored as unload endpoint
→ front switch changes present → absent
→ debounce
→ motor stops
→ idle/unloaded


BUS IDENTITY

physical serial derived from MCU UID
→ logical AMS ID assigned at runtime
→ assignment persisted
→ transient registration performed with printer
→ heartbeat loss resets registration, not permanent identity
→ host return re-registers automatically
```

---

# Project relationship and responsibility

This fork is an interoperability project built on the original BMCU work. It is not official Bambu Lab firmware and is not affiliated with Bambu Lab.

Bambu Lab, AMS, AMS Lite, and related product names are trademarks of their respective owner.

Hardware modifications and third-party firmware are used at your own risk. Verify wiring, firmware target, and mechanical clearances before operating the feeder.

For the original BMCU project, hardware documentation, broader firmware variants, and upstream development, see:

https://github.com/jarczakpawel/BMCU-C-PJARCZAK
