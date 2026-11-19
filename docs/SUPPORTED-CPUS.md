# Supported Processors (CPUs) — ASRock H61M-S1 PLUS + Coreboot

This document lists **all Socket LGA1155 processors** compatible with the **ASRock H61M-S1 PLUS** (`H61M-VS4 G/A 1.00`) motherboard and this **Coreboot + EDK2** firmware port (`v26.11.2`).

---

## 1. Platform & Firmware CPU Support Summary

| Property | Details |
|---|---|
| **Socket & Chipset** | Intel Socket **LGA1155** (`Socket H2`), Intel **H61 Express** PCH (`8086:1c5c`, Cougar Point B3) |
| **Coreboot CPU Driver** | `src/cpu/intel/model_206ax/model_206ax_init.c` (`cpu_table`: **CPUID `0x206a0`** Sandy Bridge all steppings & **CPUID `0x306a0`** Ivy Bridge all steppings) |
| **Bundled Intel Microcode** | Pre-RAM updated via `3rdparty/intel-microcode` (`CONFIG_MICROCODE_UPDATE_PRE_RAM=y`):<br>• **`06-2a-07` (Sandy Bridge D2)**: Revision **`0x2f`** (date `2019-02-17`, CPUID `0x206a7`)<br>• **`06-3a-09` (Ivy Bridge E1)**: Revision **`0x21`** (date `2019-02-13`, CPUID `0x306a9`) |
| **Intel ME Firmware** | `ME 8.1.20.1336` — natively supports **both** 2nd-Gen Sandy Bridge and 3rd-Gen Ivy Bridge (ASRock P1.10 shipped Ivy-ready out of the box) |
| **VRM & TDP Ceiling** | `UP701` Richtek `RT8876` **3+1 phase** VR12/SVID controller (`3` `VCORE` phases + `1` `VAXG` IGD phase, **unheatsinked VRM MOSFETs**):<br>• **Official Maximum TDP**: **95 W**<br>• **Recommended Sweet Spot**: **≤ 77 W** for continuous 100% load / enclosed airflow (`77 W` Ivy Bridge quad-cores run effortlessly!) |
| **Overclocking** | Intel H61 chipset **locks core multiplier ratios** (`K`-series unlocked CPUs such as `i7-3770K` / `i5-3570K` work cleanly at stock + Turbo Boost clocks only; zero BCLK/multiplier OC) |

---

## 2. Critical Compatibility Notes Before Upgrading

1. **Integrated Graphics (`libgfxinit`) Requires a CPU With Intel HD Graphics**:
   - Models marked **`None` under IGD** (e.g., `Xeon E3-1220/1230/1240/1270/1280` v1/v2, `Core i5-2380P/2450P/2550K`, `Core i5-3350P`) have no display engine in silicon — `VGA1` and `HDMI1` will remain dark, and you **must** install a discrete display GPU with UEFI GOP or CSM Option ROM (`CONFIG_EDK2_LOAD_OPTION_ROMS=y`) in `PCIE1` (`COM1` `0x3f8` serial console still works headless!).
   - Xeon `xxx5` SKUs (such as the hardware-verified **Xeon E3-1275 v2**!) **include Intel HD Graphics** (`P4000`/`P3000`) and work seamlessly with pure `libgfxinit` on `HDMI1`/`VGA1` AND `Tesla P4` headless compute!
2. **Memory Speeds & XMP**:
   - **3rd-Gen Ivy Bridge (`0x306a*`)**: Supports DDR3-**1600** (and higher via XMP profiles; `CONFIG_NATIVE_RAMINIT_IGNORE_XMP_REQUESTED_VOLTAGE=y` enabled).
   - **2nd-Gen Sandy Bridge (`0x206a*`)**: IMC officially caps at DDR3-**1333** (early Celeron G4xx/G5xx/Pentium G6xx at DDR3-**1066**).
   - **No ECC Support on H61**: Although Xeon `E3-1200` v1/v2 chips support ECC UDIMMs on C202/C204/C206/C216 server chipsets, the **H61 PCH fuses off ECC**. ECC UDIMMs typically fail to train or operate strictly in non-ECC mode; use standard **non-ECC DDR3 UDIMMs** (`2 × 8 GiB = 16 GiB` max).
3. **`VT-d` (IOMMU / VFIO Passthrough) & PCIe 3.0**:
   - **PCIe Gen3 (8.0 GT/s)** on `PCIE1` (`PEG10`) requires an **Ivy Bridge Core i5 / i7 / Xeon E3 v2** (all Core i3-3xxx and ALL Sandy Bridge CPUs run `PCIE1` at PCIe Gen2 5.0 GT/s).
   - **Intel `VT-d`** is fused off on `K`-series unlocked CPUs (`i7-2600K`, `i7-2700K`, `i5-2500K`, `i7-3770K`, `i5-3570K` — exceptions: `i5-3570`, `i7-3770` non-K *do* have `VT-d`!) and on most Core i3 / Pentium / Celeron parts. Verify `VT-d` if you need IOMMU / VFIO GPU passthrough.

---

## 3. Ivy Bridge (`22 nm`, CPUID `0x306a9`) — Recommended Family

### 3.1 Intel Xeon E3-1200 v2 Series (`Ivy Bridge-WS`)

| CPU Model | Cores / Threads | Base / Turbo (GHz) | L3 Cache | TDP | Integrated Graphics (`IGD`) | PCIe / Max DDR3 | `VT-d` | Coreboot Status & Notes |
|---|---:|---|---:|---:|---|---|---|---|
| **Xeon E3-1275 v2** | **4C / 8T** | **3.50 / 3.90** | **8 MiB** | **77 W** | **HD P4000 (`0x016a`)** | **Gen3 / 1600** | **Yes** | **HARDWARE-VERIFIED** — Daily driver test CPU (`libgfxinit` 4K + `VT-d` + S3 + Tesla P4 vGPU) |
| **Xeon E3-1290 v2** | 4C / 8T | 3.70 / 4.10 | 8 MiB | 87 W | None (`Headless`) | Gen3 / 1600 | Yes | Fastest LGA1155 chip; needs dGPU (`87 W` near VRM limit under sustained AVX) |
| **Xeon E3-1280 v2** | 4C / 8T | 3.60 / 4.00 | 8 MiB | 69 W | None (`Headless`) | Gen3 / 1600 | Yes | Great efficiency; needs dGPU or `COM1` headless operation |
| **Xeon E3-1270 v2** | 4C / 8T | 3.50 / 3.90 | 8 MiB | 69 W | None (`Headless`) | Gen3 / 1600 | Yes | Needs dGPU or `COM1` headless; very cool 69 W TDP |
| **Xeon E3-1265L v2** | 4C / 8T | 2.50 / 3.50 | 8 MiB | 45 W | HD 2500 (`0x0152`) | Gen3 / 1600 | Yes | Excellent low-power 4C/8T server SKU with working IGD |
| **Xeon E3-1245 v2** | 4C / 8T | 3.40 / 3.80 | 8 MiB | 77 W | HD P4000 (`0x016a`) | Gen3 / 1600 | Yes | Same silicon family as verified `E3-1275 v2` (`100 MHz` lower) |
| **Xeon E3-1240 v2** | 4C / 8T | 3.40 / 3.80 | 8 MiB | 69 W | None (`Headless`) | Gen3 / 1600 | Yes | Popular value 4C/8T; requires dGPU or headless `COM1` |
| **Xeon E3-1230 v2** | 4C / 8T | 3.30 / 3.70 | 8 MiB | 69 W | None (`Headless`) | Gen3 / 1600 | Yes | Very popular homelab chip; requires dGPU or headless `COM1` |
| **Xeon E3-1225 v2** | 4C / 4T | 3.20 / 3.60 | 8 MiB | 77 W | HD P4000 (`0x016a`) | Gen3 / 1600 | Yes | Working IGD (`No Hyper-Threading`) |
| **Xeon E3-1220 v2** | 4C / 4T | 3.10 / 3.50 | 8 MiB | 69 W | None (`Headless`) | Gen3 / 1600 | Yes | Needs dGPU (`No HT`) |
| **Xeon E3-1220L v2** | 2C / 4T | 2.30 / 3.50 | 3 MiB | 17 W | None (`Headless`) | Gen3 / 1600 | Yes | Ultra-low-power dual-core; needs dGPU or `COM1` headless |

### 3.2 Intel Core i7 / i5 / i3 3000-Series (`Ivy Bridge`)

| CPU Model | Cores / Threads | Base / Turbo (GHz) | L3 Cache | TDP | Integrated Graphics (`IGD`) | PCIe / Max DDR3 | `VT-d` | Coreboot Notes |
|---|---:|---|---:|---:|---|---|---|---|
| **Core i7-3770K** | 4C / 8T | 3.50 / 3.90 | 8 MiB | 77 W | HD 4000 (`0x0162`) | Gen3 / 1600 | **No** | Supported at stock/Turbo clocks (multiplier locked by H61) |
| **Core i7-3770** | 4C / 8T | 3.40 / 3.90 | 8 MiB | 77 W | HD 4000 (`0x0162`) | Gen3 / 1600 | **Yes** | Nearly identical to verified `E3-1275 v2` (`libgfxinit` + `VT-d`) |
| **Core i7-3770S** | 4C / 8T | 3.10 / 3.90 | 8 MiB | 65 W | HD 4000 (`0x0162`) | Gen3 / 1600 | Yes | Cool 65 W `77 W`-class performer |
| **Core i7-3770T** | 4C / 8T | 2.50 / 3.70 | 8 MiB | 45 W | HD 4000 (`0x0162`) | Gen3 / 1600 | Yes | Coolest full-featured 8T Core i7 |
| **Core i5-3570K** | 4C / 4T | 3.40 / 3.80 | 6 MiB | 77 W | HD 4000 (`0x0162`) | Gen3 / 1600 | **No** | Runs at stock/Turbo clocks |
| **Core i5-3570 / 3570S / 3570T** | 4C / 4T | 2.3–3.4 / 3.3–3.8 | 6 MiB | 45–77 W | HD 2500 (`0x0152`) | Gen3 / 1600 | **Yes** | Full `VT-d` + `libgfxinit` `HDMI1`/`VGA1` |
| **Core i5-3550 / 3550S** | 4C / 4T | 3.0–3.3 / 3.7 | 6 MiB | 65–77 W | HD 2500 (`0x0152`) | Gen3 / 1600 | Yes | Supported |
| **Core i5-3475S** | 4C / 4T | 2.90 / 3.60 | 6 MiB | 65 W | HD 4000 (`0x0162`) | Gen3 / 1600 | Yes | Supported |
| **Core i5-3470 / 3470S / 3470T** | 4C / 4T (T: 2C/4T) | 2.9–3.2 / 3.6 | 3–6 MiB | 35–77 W | HD 2500 (`0x0152`) | Gen3 / 1600 | Yes | Supported (`3470T` is 2C/4T with HT) |
| **Core i5-3450 / 3450S** | 4C / 4T | 2.8–3.1 / 3.5 | 6 MiB | 65–77 W | HD 2500 (`0x0152`) | Gen3 / 1600 | No | Supported |
| **Core i5-3350P** | 4C / 4T | 3.10 / 3.30 | 6 MiB | 69 W | **None** | Gen3 / 1600 | No | Requires discrete GPU |
| **Core i5-3340 / 3340S / 3330 / 3330S** | 4C / 4T | 2.7–3.1 / 3.2–3.3 | 6 MiB | 65–77 W | HD 2500 (`0x0152`) | Gen3 / 1600 | No (`3330/3340`) | Supported |
| **Core i3-3250 / 3240 / 3220 / 3210** | 2C / 4T | 3.20–3.50 (No Turbo) | 3 MiB | 55 W | HD 2500 (`0x0152`) | Gen2 / 1600 | No | Supported (`-T` 35 W low-power variants also supported) |
| **Core i3-3245 / 3225** | 2C / 4T | 3.30–3.40 (No Turbo) | 3 MiB | 55 W | HD 4000 (`0x0162`) | Gen2 / 1600 | No | Higher-tier HD 4000 on i3 (`libgfxinit` supported) |

### 3.3 Intel Pentium & Celeron (`Ivy Bridge`)

| CPU Series | Cores / Threads | Base (GHz) | L3 Cache | TDP | Integrated Graphics (`IGD`) | PCIe / Max DDR3 | `VT-d` | Coreboot Notes |
|---|---:|---|---:|---:|---|---|---|---|
| **Pentium G2140 / G2130 / G2120 / G2100T** | 2C / 2T | 2.60–3.30 | 3 MiB | 35–55 W | Intel HD Graphics (IvB) | Gen2 / 1600 | No | Supported (lacks `AVX`/`AES-NI`/`HT`) |
| **Pentium G2030 / G2020 / G2010** (`+T` 35W) | 2C / 2T | 2.50–3.00 | 3 MiB | 35–55 W | Intel HD Graphics (IvB) | Gen2 / 1333 | No | Supported (`DDR3-1333` max on G20xx) |
| **Celeron G1630 / G1620 / G1610** (`+T` 35W) | 2C / 2T | 2.30–2.80 | 2 MiB | 35–55 W | Intel HD Graphics (IvB) | Gen2 / 1333 | No | Supported entry-level CPU |

---

## 4. Sandy Bridge (`32 nm`, CPUID `0x206a7`)

All Sandy Bridge LGA1155 models are supported natively by Coreboot `model_206ax` + bundled `06-2a-07` (`rev 0x2f`) microcode. Note **95 W TDP** approaches the upper thermal limit of the board's unheatsinked 3+1 VRM under sustained synthetic load; ensure good case airflow across `UP701`/MOSFETs when running 95 W quads.

### 4.1 Intel Xeon E3-1200 v1 Series (`Sandy Bridge-WS`)

| CPU Model | Cores / Threads | Base / Turbo (GHz) | L3 Cache | TDP | Integrated Graphics (`IGD`) | PCIe / Max DDR3 | `VT-d` | Coreboot Notes |
|---|---:|---|---:|---:|---|---|---|---|
| **Xeon E3-1290** | 4C / 8T | 3.60 / 4.00 | 8 MiB | **95 W** | None (`Headless`) | Gen2 / 1333 | Yes | Max VRM TDP; needs dGPU + VRM airflow |
| **Xeon E3-1280 / E3-1270 / E3-1240 / E3-1230** | 4C / 8T | 3.2–3.5 / 3.6–3.9 | 8 MiB | 80–95 W | None (`Headless`) | Gen2 / 1333 | Yes | Requires dGPU or headless `COM1` |
| **Xeon E3-1275 / E3-1245 / E3-1235** | 4C / 8T | 3.2–3.4 / 3.6–3.8 | 8 MiB | **95 W** | HD P3000 (`0x0112`/`0x0122`) | Gen2 / 1333 | Yes | Working IGD (`libgfxinit`) + `VT-d` |
| **Xeon E3-1225** | 4C / 4T | 3.10 / 3.40 | 6 MiB | **95 W** | HD P3000 | Gen2 / 1333 | Yes | Working IGD (`No HT`) |
| **Xeon E3-1220 / E3-1220L / E3-1260L** | 2–4C / 4–8T | 2.2–3.1 / 3.3–3.4 | 3–8 MiB | 20–80 W | `1260L`: HD 2000; others: None | Gen2 / 1333 | Yes | `E3-1260L` (`45 W`, 4C/8T) has HD 2000 IGD |

### 4.2 Intel Core i7 / i5 / i3 2000-Series (`Sandy Bridge`)

| CPU Model | Cores / Threads | Base / Turbo (GHz) | L3 Cache | TDP | Integrated Graphics (`IGD`) | PCIe / Max DDR3 | `VT-d` | Coreboot Notes |
|---|---:|---|---:|---:|---|---|---|---|
| **Core i7-2700K / 2600K** | 4C / 8T | 3.4–3.5 / 3.8–3.9 | 8 MiB | **95 W** | HD 3000 | Gen2 / 1333 | **No** | Multiplier locked by H61; `libgfxinit` supported |
| **Core i7-2600 / 2600S** | 4C / 8T | 2.8–3.4 / 3.8 | 8 MiB | 65–95 W | HD 2000 | Gen2 / 1333 | **Yes** | Full `VT-d` + `libgfxinit` |
| **Core i5-2550K / 2500K / 2500 / 2400 / 2320 / 2310 / 2300** | 4C / 4T | 2.8–3.4 / 3.1–3.8 | 6 MiB | **95 W** | HD 2000 (`2500K`: HD 3000; `2550K/2450P/2380P`: None) | Gen2 / 1333 | `2400/2500` non-K only | `-S` (`65 W`) & `-T` (`35–45 W`, e.g., `2500T`, `2390T`) run cooler on VRM |
| **Core i3-2130 / 2125 / 2120 / 2105 / 2100** (`+T` 35W) | 2C / 4T | 2.50–3.40 (No Turbo) | 3 MiB | 35–65 W | HD 2000 (`2105/2125`: HD 3000) | Gen2 / 1333 | No | Supported |

### 4.3 Intel Pentium & Celeron (`Sandy Bridge`)

| CPU Series | Cores / Threads | Base (GHz) | L3 Cache | TDP | Integrated Graphics (`IGD`) | PCIe / Max DDR3 | `VT-d` | Coreboot Notes |
|---|---:|---|---:|---:|---|---|---|---|
| **Pentium G870 / G860 / G850 / G840** (`G860T`) | 2C / 2T | 2.60–3.10 | 3 MiB | 35–65 W | Intel HD Graphics (SNB) | Gen2 / 1333 | No | Supported (`DDR3-1333`) |
| **Pentium G645 / G640 / G630 / G620** (`+T` 35W) | 2C / 2T | 2.20–2.90 | 3 MiB | 35–65 W | Intel HD Graphics (SNB) | Gen2 / 1066 | No | Supported (`DDR3-1066` IMC cap) |
| **Celeron G555 / G550 / G540 / G530** (`+T` 35W) | 2C / 2T | 1.90–2.70 | 2 MiB | 35–65 W | Intel HD Graphics (SNB) | Gen2 / 1066 | No | Supported |
| **Celeron G470 / G465 / G460 / G440** | 1C / 1–2T | 1.60–2.00 | 1–1.5 MiB | 35 W | Intel HD Graphics (SNB) | Gen2 / 1066 | No | Single-core budget SKUs; supported |

---

## 5. Unsupported Processors (Do NOT Install)

- **LGA1150 / LGA1151 / LGA1156 / LGA2011 CPUs**: Physically & electrically incompatible with LGA1155.
- **Any > 95 W CPU (if custom/ES)**: Exceeds the ASRock H61M-S1 PLUS `UP701` (`RT8876`) 3-phase `VCORE` thermal design envelope.
