# คู่มือ RetroSoC Full-Chip Implementation
## LibreLane 3.0.5 + IHP SG13G2 — ขั้นตอนรันและรายงานตรวจโค้ด

วันที่ตรวจล่าสุด: 30 กันยายน 2026 • ภาษาไทยพร้อมศัพท์วิศวกรรม

**สถานะ:** ตรวจ source ของ upstream HEAD และทดสอบ build tooling บางส่วนแล้ว ชุดส่งมอบมี source snapshot ที่แก้ blocker, `config.yaml`, staged runner และ regression tests แต่ยังไม่ได้รัน RTL simulation, synthesis, placement/routing, STA, DRC หรือ LVS ของทั้งชิปในสภาพแวดล้อมนี้ จึงยังไม่รับรองว่า RTL-to-GDSII ผ่านครบ หรือว่าไฟล์ที่ได้พร้อม tape-out

คำว่า “พร้อมรัน” ในชุดนี้หมายถึงมีลำดับคำสั่งและไฟล์ประกอบที่อ้างอิงโค้ดจริง ไม่ต้องสร้าง config/SDC ขึ้นใหม่จากตัวอย่าง ส่วนผล EDA ต้องรันและเก็บหลักฐานตาม gate ในแต่ละขั้น ก่อนถือว่าผ่าน

## 1. Baseline ที่ใช้จริง

| รายการ | ค่าที่ตรวจจาก source |
|---|---|
| Repository | https://github.com/retroSoC/retroSoC |
| Commit | `7a58375c0bd7c24b98e36a5451288e0a0e5666dc` |
| Profile | `configs/ci/ihp130.mk` |
| SoC / top | `MINI` / `retrosoc_asic` |
| Management CPU | Hazard3; interface `CORE` แบบเก่าถูกถอดออกแล้ว |
| ISA / APP / linker | `RV32IM` / `bringup` / `ld2_psram` |
| PDK name ใน Make | `IHP130` |
| PDK name ใน LibreLane | `ihp-sg13g2` |
| PDK revision | `970a7688e7dcce2a6172797df9ef47bde2f60f9f` |
| Standard-cell / IO library | `sg13g2_stdcell` / `sg13g2_io` |
| LibreLane | `3.0.5` ตาม `physical/librelane/mini/scripts/doctor.py` |
| External / audio clock | 72 MHz / 18.432 MHz |
| CLINT timebase | 1 MHz |
| Features | `HAVE_PLL=NO`, `HAVE_SRAM_IF=YES`, `HAVE_SRAM_MACRO=YES`, `HAVE_SVA=NO` |
| Die / core bounds | `[0,0,8000,8000]` / `[365,365,7635,7635]` µm |
| Placement density target | 45% ของพื้นที่ตามนิยามเครื่องมือ ไม่ใช่ผล utilization ที่วัดแล้ว |

ตัวเลข die และ density เป็นแผนเริ่มต้นจาก generator ไม่ใช่ผลการ optimize หรือ PPA ที่ผ่านแล้ว พื้นที่ die เท่ากับ 64 mm²; core rectangle เท่ากับ 52.8529 mm² ก่อนหัก macros/obstructions

### โครงสร้างการ implementation

นี่คือ single-level `Chip` flow: RTL ของ `retrosoc_asic` → synthesis → pad ring และ SRAM placement → PDN → standard-cell placement/routing → extraction/STA และ physical verification → GDSII พร้อม finishing steps ของ Chip flow ไม่มีขั้นตอน harden digital-core เป็น macro แยกใน implementation นี้ Baseline ปัจจุบันตั้ง `RUN_CTS=false` และปิด post-CTS repair จึงต้องถือว่า clock-tree sign-off ยังเป็น milestone ที่ต้องเปิดและ validate แยก

แยก source of truth ดังนี้:

| สิ่งที่ต้องแก้ | Source of truth |
|---|---|
| Feature/clock/profile | `configs/ci/ihp130.mk`, root `Makefile` |
| ขาและ pad bindings | `rtl/mini/pin_map/pin_map.json`, `generate_pin_map.py` |
| Internal topology | `rtl/mini/integration/soc_topology.json` |
| Clock/reset inventory | `rtl/mini/integration/clock_reset_domains.json` |
| Full-chip configuration | `physical/librelane/mini/scripts/generate_chip_config.py` |
| Timing constraints | `physical/librelane/mini/scripts/generate_sdc.py` |
| Power network | `physical/librelane/mini/pdn_cfg.tcl` |
| Macro synthesis declarations | `physical/librelane/mini/sram_blackboxes.vh` |
| External revisions / archives | `dependencies/dependencies.lock.json` |

ไม่แก้ `build/.../config.yaml` เป็นทางแก้ถาวร เพราะ generator จะสร้างทับได้ ให้แก้ source และเปลี่ยน build session เมื่อประเมิน configuration ใหม่

## 2. ผลตรวจและการแก้ build tooling

### 2.1 ข้อผิดพลาดที่แก้แล้วใน source snapshot

| จุด | หลักฐาน / ผลกระทบ | การแก้ |
|---|---|---|
| `scripts/config_key.py` | `--help` ล้มจริงบน Python 3.12 ด้วย `unsupported format character 'Y'` | escape `%` สำหรับ argparse โดยไม่เปลี่ยน timestamp format |
| `physical/librelane/mini/Makefile` | upstream สร้าง `config.json` ไม่ตรงข้อกำหนด `config.yaml` | เปลี่ยน output เป็น `config.yaml`; เนื้อหาใช้ JSON-compatible subset ของ YAML |
| package run tag | ตัวรันรองรับ `LIBRELANE_RUN_TAG` แต่ packaging อ่าน `runs/current` ตายตัว | เพิ่ม `--run-tag`; Make ส่ง tag ให้ package |

มีการเปลี่ยน build/tooling เท่านั้น พร้อม regression tests สำหรับ help string, ชื่อ `config.yaml` และ non-current run tag ไม่มีการเปลี่ยน RTL, pin interface, PDK revision, macro placement หรือ SDC

### 2.2 ประเด็นที่แก้ด้วยขั้นตอนการใช้งาน

- README บอกใช้ LibreLane จาก development shell แต่ `development_environment.py` ไม่มี LibreLane ใน `DEFAULT_TOOLS` และ `flake.nix` เป็น regression environment จึงต้องเตรียม LibreLane 3.0.5 แยก
- requirements ระบุ Ubuntu 22.04/Python 3.10 และบังคับ wheel hashes การใช้ Python 3.12/3.14 ไม่ได้ทำให้ wheel ที่เลือกมี hash ตรงโดยอัตโนมัติ
- root Makefile default เป็น `SIMU=VCS` จึงต้องระบุ `SIMU=IVERILOG` หรือ `VERILATOR` สำหรับ open-source flow ทุกครั้ง
- `BUILD_TIMESTAMP` เปลี่ยนตามเวลาโดย default ต้อง export ค่าคงที่เพื่อให้คำสั่งต่อเนื่องใช้ variant เดียว
- runner stage `package` เรียก packaging โดยตรงหลังตรวจ result จึงไม่รัน P&R ซ้ำ

### 2.3 ขอบเขตที่ยังไม่ผ่าน qualification

ยังไม่สามารถสรุป correctness ของ RTL ทั้งระบบจากการอ่านไฟล์หรือ unit test ของ generator ได้ โดยเฉพาะ post-synthesis hierarchy ของ macro/SDC, clock mux modes, generated/forwarded interface clocks, reset recovery/removal, macro timing corners, full-chip power connectivity และ DRC/LVS ต้องตรวจด้วยเครื่องมือจริงตามขั้นต่อไป

## 3. เตรียม workspace จากชุด source พร้อมรัน

ใช้ Linux x86_64 และ path ที่ไม่มีช่องว่าง เพื่อสอดคล้องกับ Make recipes ปัจจุบัน งานทดสอบนี้ควรมี checkout แยกจากงานที่กำลังรันอยู่

แตก `RetroSoC-IHP-SG13G2-LibreLane3-Ready.zip` ซึ่งมี source snapshot ที่ตรึง commit และการแก้ไขทั้งหมดแล้ว:

```bash
mkdir -p "$HOME/workshop"
cd "$HOME/workshop"
unzip /path/to/RetroSoC-IHP-SG13G2-LibreLane3-Ready.zip
cd RetroSoC-IHP-SG13G2-LibreLane3-Ready
export RETROSOC_ROOT="$PWD"
git diff --check
git diff --stat
```

**Gate:** อ่าน `BASELINE.md` แล้ว hash ของ upstream และ template ตรงค่าที่ระบุ, `git diff --check` ไม่มี error และ `python3 scripts/config_key.py --help` ทำงานได้

## 4. เตรียม regression/source-generation environment

### 4.1 เส้นทางอ้างอิง: Ubuntu 22.04 + Python 3.10

ใช้ Ubuntu 22.04 x86_64 native/VM/WSL2 ที่เข้าถึง package servers ได้ ถ้าเครื่องหลักเป็น Ubuntu 24.04 ให้สร้าง Ubuntu 22.04 environment แยกสำหรับ baseline นี้ หรือจัดทำและทดสอบ requirement lock สำหรับ Python ที่ต้องการก่อน ไม่ใช้การลบ hash เพื่อให้ติดตั้งผ่าน

คำสั่งด้านล่างมาจาก prerequisites ใน repository; ต้องมีสิทธิ์ติดตั้งแพ็กเกจในเครื่องของผู้ใช้:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends --yes \
  bzip2 ca-certificates ccache clang-format-14 g++ git libfl2 \
  libgoogle-perftools4 libunwind8 make mold numactl python3 \
  python3-pip python3-venv xz-utils zlib1g

cd "$RETROSOC_ROOT"
python3 --version
python3 scripts/dependency_lock.py --lock dependencies/dependencies.lock.json
python3 scripts/development_environment.py bootstrap
source .cache/retrosoc/development/activate.sh
python3 scripts/development_environment.py check
python3 -c 'import sys, pyslang; print(sys.executable); print(pyslang.__file__)'
export RETROSOC_SOURCE_PYTHON="$RETROSOC_ROOT/.cache/retrosoc/development/venv/bin/python"
```

`bootstrap` ใช้เวอร์ชันและ checksum จาก lock; อย่าเพิ่ม `pip install --upgrade` หลัง bootstrap โดยไม่บันทึก dependency change ถ้า venv เดิมสร้างด้วย Python คนละรุ่น ให้เก็บ venv เดิมเป็น backup แล้วสร้างใหม่ด้วย interpreter ที่เลือก หลีกเลี่ยงการย้าย venv ไปใช้คนละ path เพราะ script shebang อาจฝัง absolute path

### 4.2 เลือกเฉพาะ dependencies ของ IHP130

```bash
cd "$RETROSOC_ROOT"
export BUILD_TIMESTAMP="$(date +%Y-%m-%d-%H-%M)"
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG setup
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG doctor
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG config
```

`setup` ครอบคลุม MPW user design, cluster IP, third-party IP, PDK และ application inputs ส่วน `setup-regression` จะเตรียมหลาย PDK จึงไม่จำเป็นสำหรับเป้าหมาย IHP full chip เพียงอย่างเดียว

```bash
git -C physical/pdk/IHP-Open-PDK rev-parse HEAD
python3 - <<'PY'
import json
from pathlib import Path
lock = json.loads(Path('dependencies/dependencies.lock.json').read_text())
for name in ('mpw', 'hazard3', 'pdk_ihp130'):
    item = lock['sources'][name]
    print(name, item['revision'], item['destination'])
PY
```

**Gate:** PDK revision ตรง lock และ source generator import `pyslang` ได้ การพบ executable เพียงอย่างเดียวยังไม่เท่ากับ functional test ผ่าน

### 4.3 ปัญหา Python ที่พบได้

| อาการ | ตรวจและแก้ |
|---|---|
| `%Y` ใน `config_key.py` | ชุดนี้แก้แล้ว; ทดสอบ `python3 scripts/config_key.py --help` ก่อน bootstrap/Make |
| pip hash mismatch | ตรวจ `python3 --version`, path ของ venv และ requirements ที่ใช้ เก็บ expected/actual hash และชื่อ wheel; ใช้ interpreter baseline หรือปรับ lock ด้วยการตรวจแหล่งต้นทาง |
| `ModuleNotFoundError: pyslang` | ตรวจ interpreter ที่ recipe เรียก; ส่ง `PYTHON` และ `LIBRELANE_SOURCE_PYTHON` เป็น venv Python |
| `libstdc++.so.6` / ABI error | ตรวจ `ldd` ของ pyslang shared object ใน environment ที่เกิดปัญหาจริง; อย่าแก้ด้วย symlink ไลบรารีสุ่มรุ่น |
| `bsub` หรือ `vcs` ไม่พบ | กำหนด `SIMU=IVERILOG`/`VERILATOR`; ไม่ใช่ prerequisite ของ open-source run |
| `riscv32-unknown-elf-gcc` ไม่พบ | เปิด activation ของ locked tools; อย่าเปลี่ยนเป็น riscv64 prefix โดยไม่ตรวจ build variables/ISA/ABI ของ firmware |

## 5. Functional gates ก่อน physical design

ทำส่วนนี้ใน regression environment ที่ activation ถูกต้อง ก่อนสลับไป LibreLane shell

```bash
cd "$RETROSOC_ROOT"
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG check-pin-map
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG check-soc-topology
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG check-clock-reset-domains

make CONFIG=configs/ci/ihp130.mk SIMU=VERILATOR \
  APP=ci_smoke firmware sim

make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG \
  RTL_SIM_TIMEOUT=5200000 sim-asm
```

`APP=ci_smoke` เป็น acceptance image ตาม CI และสร้างคนละ configuration hash จาก `APP=bringup` นี่เป็น functional precheck; generated inputs ของ full chip ในขั้นถัดไปจะกลับมา `APP=bringup` ตาม baseline

**เงื่อนไข simulation ผ่าน:** คำสั่งสำเร็จ, log มี `SIM_TEST_PASS` และไม่มี `SIM_TEST_FAIL`, `SIM_TEST_TIMEOUT`, `FAILED`, `FATAL`, `assertion failed` หรือ `%Error` การเห็น UART boot banner เพียงอย่างเดียวไม่พอ

ทดสอบ synthesis/netlist แบบ smoke ก่อน full chip ถ้าต้องการแยก front-end/RTL issue:

```bash
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG SYNTH=YOSYS synth
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG \
  SIM_FIRMWARE_NAME=retrosoc_asm RTL_SIM_TIMEOUT=5200000 netsim
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG STA=OPENSTA sta
```

Flow smoke และ constraints ของมันไม่ใช่หลักฐาน timing/physical verification ของ full-chip run ต้องเก็บ log แยกและระบุ scope

## 6. เตรียม LibreLane 3.0.5 แยกจาก regression tools

ต้องติดตั้ง Nix พร้อม flakes ตามเอกสาร LibreLane และ binary cache ของ fossi-foundation ก่อน หากมี Nix อยู่แล้ว ให้ตรวจ configuration ตาม upstream installation link ในท้ายคู่มือ

```bash
cd "$HOME/workshop"
git clone https://github.com/librelane/librelane.git librelane-3.0.5
cd librelane-3.0.5
git checkout --detach 3.0.5
export LIBRELANE_CHECKOUT="$PWD"
nix develop "$LIBRELANE_CHECKOUT"
```

หลังเข้า shell:

```bash
librelane --version
python3 -c 'from librelane.flows import Flow; print(Flow.factory.get("Chip"))'
yosys -Q -T -p 'plugin -i slang; help read_slang'
command -v openroad klayout magic netgen
librelane --smoke-test
```

`librelane --smoke-test` เป็นการตรวจ installation ด้วย example ของ LibreLane ไม่ใช่ RetroSoC; อาจต้องดาวน์โหลด PDK เพิ่มตาม example การรัน RetroSoC ใช้ manual-PDK path ของ repository โดยเฉพาะ

**Gate:** บรรทัดเวอร์ชันต้องเป็น `LibreLane v3.0.5`, import `Chip` ได้ และ yosys-slang พร้อมใช้งาน หากเครื่องมี 3.0.9 อย่าแก้ doctor ให้ยอมผ่านเฉย ๆ ให้เปิด environment ของ 3.0.5 ตาม baseline หรือทำ migration/validation แยก

source-generation Python และ LibreLane Python มีหน้าที่ต่างกัน:

```bash
export RETROSOC_SOURCE_PYTHON="$RETROSOC_ROOT/.cache/retrosoc/development/venv/bin/python"
"$RETROSOC_SOURCE_PYTHON" -c 'import sys, pyslang; print(sys.executable); print(pyslang.__file__)'
python3 -c 'import sys, librelane; print(sys.executable); print(librelane.__file__)'
```

ใช้ shell นี้ต่อไป และไม่ source regression activation ทับ PATH ของ LibreLane ถ้า environment variables จาก Nix ทำให้ source Python import ไม่ผ่าน ต้องแก้ isolation ให้ import test ทั้งสองบรรทัดผ่านก่อนรัน Make

## 7. สร้าง full-chip inputs และตรวจ doctor

ตั้งค่าตัวแปรให้ตรง session เดิม ถ้าเปิด terminal ใหม่ ต้องนำ `BUILD_TIMESTAMP` เดิมกลับมาใช้ ไม่ตั้งวันที่ใหม่โดยไม่ตั้งใจ

```bash
cd "$RETROSOC_ROOT"
python3 scripts/run_fullchip.py \
  --repo "$RETROSOC_ROOT" \
  --librelane-python "$(command -v python3)" \
  --stages preflight,input,doctor
```

runner ใช้ `CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG APP=bringup` และส่ง Python ทั้งสองตัวอย่างชัดเจน สำหรับคำสั่ง Make โดยตรง:

```bash
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG APP=bringup \
  PYTHON="$RETROSOC_SOURCE_PYTHON" \
  LIBRELANE_SOURCE_PYTHON="$RETROSOC_SOURCE_PYTHON" \
  LIBRELANE_PYTHON="$(command -v python3)" librelane-doctor
```

### Outputs ที่ต้องมี

อ่าน `VARIANT_ROOT` จาก `make config` แล้วตั้ง `VARIANT_ROOT` เป็น path จริงที่พิมพ์ออกมา ไม่เลือกด้วย wildcard ที่อาจตรงหลาย variants

| Path ภายใต้ `VARIANT_ROOT` | หน้าที่ |
|---|---|
| `physical/librelane/mini/chip/input/retrosoc_asic_sources.sv` | exported source พร้อม inline headers/defines |
| `physical/librelane/mini/chip/input/retrosoc_asic.sdc` | generated full-chip constraints |
| `physical/librelane/mini/chip/input/bondpad_70x70.gds` | PCell-generated bondpad |
| `physical/librelane/mini/chip/config.yaml` | generated LibreLane config |
| `meta/librelane-chip-doctor.json` | version, PDK revision, config-load result, pad count |

RTL exporter ใช้ `--librelane-safe` และปรับ Hazard3 `update_nonconst` ตาม pattern ที่กำหนด ถ้า pattern ไม่ตรงต้องตรวจ dependency revision ไม่ปิด assertion ของ exporter เพื่อให้ผ่าน

Bondpad สร้างจาก PDK `bondpad.py` ด้วย diameter 70 µm, shape square และชื่อ output `bondpad_70x70.gds` ซึ่งสัมพันธ์กับ top cell name; ใช้ LEF ของ repository ที่ชื่อ master เดียวกัน ห้ามเปลี่ยนชื่อ GDS output โดยลืมเปลี่ยน contract

**Gate:** doctor JSON มี `status: passed` และ pads ไม่ซ้ำครบ 192 ตัว การผ่าน doctor หมายถึง version/path/config checks ผ่าน ไม่ได้แปลว่า synthesis หรือ DRC ผ่าน

## 8. Pad ring และ SRAM macro integration

### 8.1 Pad plan

| ด้าน | สัญญาณ + power/ground pads |
|---|---:|
| South | 33 |
| East | 52 |
| North | 48 |
| West | 59 |
| รวม | 192 |

จำนวนรวมจาก generated pad sides เท่ากับ 192 placements โดยมี supply pads 80 ตัว: core VDD/VSS อย่างละ 24 และ IO VDD/VSS อย่างละ 16 ค่า doctor คาด 111 active signal pads บวก supply pads; ต้อง reconcile รายการที่สร้างจริงกับ canonical pin map ก่อน sign-off และห้ามแก้ตัวเลข checker เพื่อให้ผ่าน

ชื่อ power-pad instance ใน configuration มี escaped indices เช่น `vdd_pads\[0\].vdd_pad` ส่วน signal pads ใช้ hierarchical name เช่น `u_extclk_i_pad.u_sg13g2_IOPadIn` ให้เทียบกับ netlist หลัง synthesis ก่อนแก้ชื่อ

SG13G2 IO cells ใน PDK ที่ตรวจมีตัวอย่าง footprint 80 × 180 µm; ring มี edge spacing และ bondpad offsets จาก PDK config อย่าคำนวณ die minimum จากผลรวมความกว้าง pad อย่างเดียว ต้องรวม corner, spacing, bondpad และ seal ring

IHP wrapper ไม่ได้ให้ programmable pull-up/pull-down/Schmitt behavior เท่ากับความสามารถเชิงตรรกะทุกอย่างของ generic GPIO interface ต้องบันทึกข้อจำกัดนี้ใน pin specification ของบอร์ด

### 8.2 SRAM ที่อยู่ใน configuration จริง

| Macro | จำนวน | ตำแหน่งเริ่มต้น µm | Orientation |
|---|---:|---|---|
| `RM_IHPSG13_1P_4096x16_c3_bm_bist` | 2 | high `[500,500]`, low `[1000,500]` | N |
| `RM_IHPSG13_1P_4096x8_c3_bm_bist` | 1 | ECC `[1500,500]` | N |

full hierarchy prefix คือ:

```text
u_retrosoc.u_apb4_periph.u_apb4_usb2.u_link_domain.u_packet_store.u_packet_ram.u_packet_ram
```

suffix คือ `.u_data_high`, `.u_data_low`, `.u_ecc` ตามลำดับ

packet RAM 3 ตัวมีความจุรวม 4096 × 40 bits = 20 KiB นอกจากนี้ profile ตั้ง `HAVE_SRAM_MACRO=YES` และ generator เพิ่ม `RM_IHPSG13_1P_1024x32_c2_bm_bist` อีก 8 instances สำหรับ on-chip SRAM 32 KiB ดังนั้น macro inventory หลัง synthesis ต้องครบ 11 instances

LEF ของ 4096×16 ที่ตรวจมีขนาด 416.64 × 618.3 µm ตำแหน่งใน config เป็นแผนเริ่มต้น ต้องตรวจ overlap, halo, pin accessibility และ PDN ใน OpenROAD จริง

`MACROS` ต้องอ้าง GDS, LEF, Liberty, CDL และ synthesis header ให้ตรง master เดียวกัน สัญญาณ BIST ใน wrapper ถูกผูก inactive; header เป็น blackbox สำหรับ synthesis และไม่ใช่ behavioral model สำหรับ simulation

Macro power hooks มี 2 รายการต่อ instance รวม 6 รายการ:

```text
<instance> VDD VSS VDDARRAY! VSS!
<instance> VDD VSS VDD!      VSS!
```

อย่าลบ `!` จากชื่อ power pin เพื่อให้สะดวก เพราะเป็นชื่อ pin จริงของ macro views

**Corner ที่ต้องตรวจเพิ่ม:** config map fast operating corner ที่ชื่อ `*_fast_1p32V_m40C` ไปใช้ SRAM Liberty `_fast_1p32V_m55C.lib` ซึ่งไฟล์มีจริงใน PDK ที่ pin ไว้ แต่การมีไฟล์ไม่ได้ทำให้ temperature mismatch เป็น qualified timing corner ต้องบันทึกความต่างนี้และประเมินตาม characterization/foundry guidance ก่อน signoff

## 9. Synthesis และ hierarchy gate

```bash
python3 scripts/run_fullchip.py \
  --repo "$RETROSOC_ROOT" \
  --librelane-python "$(command -v python3)" \
  --jobs 4 --stages regression
```

stage `regression` รัน topology gates, Verilator `ci_smoke`, Icarus assembly test, Yosys synthesis, netlist simulation และ OpenSTA ตามลำดับ เป็น gate ก่อน P&R และหยุดทันทีเมื่อคำสั่งใดล้ม

config เปิด `USE_SLANG=True`, `SLANG_ARGUMENTS=["--keep-hierarchy"]`, `SYNTH_HIERARCHY_MODE=deferred_flatten`, `SYNTH_SHARE_RESOURCES=False` เพื่อรักษา source/hierarchy contract ของ flow นี้ ห้ามเปลี่ยนเป็น generic `read_verilog` ทั้งไฟล์โดยไม่ประเมิน SystemVerilog interfaces และ hierarchy

**ตรวจใน log/netlist:**

1. ไม่มี unresolved module/duplicate module และไม่มี unmapped logic cells
2. พบ SRAM 3 instances ตามชื่อใน `MACROS` และ pad instances ตรง pin-map
3. Source ไม่ได้รวม behavioral SRAM model เข้า synthesis พร้อม blackbox ซ้ำ
4. วิเคราะห์ inferred memories/register count ของ CPU/user design ไม่สมมติว่าถูกแทนด้วย USB SRAM
5. ไม่มี latch หรือ multi-driver ใหม่ที่ไม่ตั้งใจ; review warnings ตาม baseline ของ repository

ถ้าพบ `Unknown key` ให้ตรวจ schema ของ LibreLane 3.0.5 กับ PDK revision ก่อน ห้ามใส่ `ERROR_ON_*`, `PAD_BONDPAD_SIZE` หรือ flag จากคู่มือ OpenLane/LibreLane คนละรุ่นโดยไม่ตรวจ

ถ้า `CheckMacroInstances` ล้มในขั้นถัดไป ให้เทียบชื่อ hierarchy จาก netlist ไม่ใช่แก้ MACROS เป็นชื่อที่เดา และอย่าถอด macro checker เพื่อให้ flow ไปต่อ

## 10. Timing constraints: สิ่งที่สร้างและสิ่งที่ต้องทบทวน

| Clock | จุดอ้างอิงใน generator | Period |
|---|---|---:|
| External | output `p2c` ของ external clock pad | 13.8888889 ns |
| System | `u_rcu.u_sys_clk_buf/clk_o` generated จาก external | divide by 1 |
| Audio | output `p2c` ของ audio pad | 54.2534722 ns |
| JTAG | output `p2c` ของ JTAG TCK pad | 100 ns |
| DVP | output `p2c` ของ GPIO10 pad | 41.6666667 ns |
| ULPI | output `p2c` ของ ULPI CLK pad | 16.6666667 ns |

SDC แยก asynchronous clock groups, ใช้ setup/hold uncertainty 0.2/0.1 ns, transition 0.1 ns, early/late derates 0.95/1.05 และสร้าง I/O delay สูงสุด 20% ของ period โดย min เป็น 0 ค่าเหล่านี้เป็น baseline ของ generator ไม่ใช่ budget ที่คำนวณจากบอร์ด/อุปกรณ์ภายนอก

### ข้อจำกัดที่ต้องทำ mode review

- GPIO11–20 ถูก assign timing group เป็น DVP ใน generator แต่ RTL multiplex pins ชุดนี้กับ I²S/SDIO และหน้าที่อื่น ดังนั้นหนึ่ง SDC ไม่ได้พิสูจน์ทุก pin-mux mode
- GPIO10 ถูกใช้เป็น DVP clock input ใน SDC แต่สามารถเป็น I²S MCLK output ในอีก mode ต้องแยก timing scenario และ case analysis ที่สอดคล้องกับ control จริง
- I²S, SDRAM, XPI และ interface ที่มี forwarded/generated clock ต้องตรวจ clock relationship และ external setup/hold ตามอุปกรณ์จริง ไม่ใช้ I/O delay 20% เป็น signoff budget โดยอัตโนมัติ
- Clock roots อยู่ที่ pad `p2c` จึงต้อง review วิธี account input clock pad delay และ board latency ใน timing contract
- `set_false_path -from` reset ports ตัดเส้นทาง reset กว้าง ต้องตรวจ recovery/removal และ asynchronous assertion/synchronous deassertion แยก
- Baseline ไม่เรียก `set_propagated_clock` และตั้ง `RUN_CTS=false`; timing ที่ได้ยังไม่ใช่ post-CTS sign-off จนกว่าจะเปิด CTS และทบทวน clock propagation ใน run tag แยก

**Gate:** ทุก `require_pins` resolve ได้หลัง synthesis, รายงาน clocks ครบ, ไม่มี unconstrained endpoint ที่ไม่อธิบาย และ review CDC/mode exceptions แล้ว ข้อความ generated-clock อยู่ใน SDC ไม่ใช่หลักฐานว่า clock propagation ถูกต้อง

## 11. Floorplan, pad ring และ PDN

```bash
python3 scripts/run_fullchip.py \
  --repo "$RETROSOC_ROOT" \
  --librelane-python "/absolute/path/to/librelane-3.0.5/bin/python" \
  --run-tag full01 --jobs 4 --stages chip
```

runner ที่แนบตั้งใจใช้ public Make contract จึงรัน `Chip` flow ทั้งสาย ไม่ผูกกับชื่อ internal LibreLane step ที่อาจเปลี่ยน ถ้าต้องหยุดวิเคราะห์ที่ PDN ให้ใช้ run database/log ของ tag นี้และคำสั่ง LibreLane 3.0.5 ที่ผ่านการตรวจในทีมก่อน อย่าเดาชื่อ `--to` step จากเวอร์ชันอื่น

PDN ใช้ 4 nets: `VDD`, `VSS`, `IOVDD`, `IOVSS`; เชื่อม lower-case pins ของ IHP IO cells ผ่าน `add_global_connection` และ supply pins ของ SRAM ผ่าน macro hooks ให้ตรวจทั้ง signal type และความต่อเนื่องทางกายภาพของ supply แต่ละชุด

core ring เริ่ม width 15 µm, spacing 5 µm; standard-cell stripe dimensions/layers ส่วนอื่นรับจาก PDK; packet RAM grid เพิ่ม Metal5 straps และเชื่อม `Metal4–Metal5` / `Metal5–TopMetal1` ตาม Tcl ปัจจุบัน

**ตรวจ ODB/DEF และ GUI:**

1. Pads เรียงครบ 192 ตัว, corners ครบ, ไม่มี pad overlap หรือ placement หลุด die
2. SRAM 3 instances อยู่ใน core, ไม่ทับกัน/rows/obstructions และมีพื้นที่ route ที่ขา
3. VDD/VSS core grid ต่อ standard cells และ macro `VDD!`, `VDDARRAY!`, `VSS!` ครบ
4. IOVDD/IOVSS ต่อ IO ring ครบและไม่ short กับ core rails; ดู failed-via/power-grid reports
5. Ring/stripes ใช้ routing layer ที่ PDK รองรับ หลีกเลี่ยงการนำชื่อ `met5` จาก PDK อื่นมาใช้ใน IHP

การผูก global net หรือเพิ่ม hook ใน config ไม่ได้พิสูจน์ connectivity ของ metal ต้องตรวจผล PDN และ extraction/LVS ต่อ

เปิด run ด้วย GUI หลังผ่าน doctor ได้ เช่นใช้ Make พร้อม Python arguments เหมือนขั้น 7 และ `LIBRELANE_RUN_TAG=pdn01 librelane-openroad` โดย target upstream ใช้ `--last-run` ด้วย ให้ตรวจ run path ที่ GUI เปิดจริงก่อนวิเคราะห์ ใน workspace ที่มีหลาย tags การเปิดไฟล์ `.odb` ของ run ที่เลือกโดยตรงช่วยลดความสับสน

## 12. Placement, baseline no-CTS และ detailed routing

```bash
python3 scripts/run_fullchip.py \
  --repo "$RETROSOC_ROOT" \
  --librelane-python "/absolute/path/to/librelane-3.0.5/bin/python" \
  --run-tag full01 --jobs 4 --stages chip,validate
```

ใช้ log และ run directory ของ `full01` แยกผล placement และ route ตามชื่อ stepจริง Baseline จะ skip CTS ตาม `RUN_CTS=false`; ต้องบันทึกสถานะนี้ในรายงานทุกครั้ง เมื่อทดลอง configuration ใหม่ให้เปลี่ยน run tag และเก็บผลเดิม

| Stage | สิ่งที่ประเมิน | เงื่อนไขเดินหน้าต่อ |
|---|---|---|
| Global/detailed placement | utilization, congestion, legal placement, macro channels | ไม่มี overlap/illegal placement; congestion มีทางแก้ |
| Clock implementation | baseline no-CTS; ตรวจ skipped step และ ideal-clock timing | ห้ามเรียกว่า post-CTS; เปิด CTS ใน experimental tag แยกก่อน sign-off |
| Global route | congestion/overflow, antenna, timing estimates | congestion และ antenna มีผลรายงานที่ review ได้ |
| Detailed route | DRC, routing connectivity | checker ผ่านหรือมี defect list ชัดเจนสำหรับแก้ |

ถ้า hold buffer มากผิดปกติ ให้ตรวจ clock definitions, min I/O delays, false paths และ clock domains ก่อนเพิ่ม buffer limits ถ้า congestion สูง ให้ review macro channels, pad fan-in, PDN obstructions และ density ก่อนใช้ `GRT_ALLOW_CONGESTION` การเปิดอนุญาต congestion ไม่ใช่การแก้ DRC

## 13. รัน full chip ถึง final views

```bash
python3 scripts/run_fullchip.py \
  --repo "$RETROSOC_ROOT" \
  --librelane-python "/absolute/path/to/librelane-3.0.5/bin/python" \
  --run-tag full01 --jobs 4 \
  --stages preflight,setup,quality,regression,input,doctor,chip,validate
```

runner จะเรียก upstream `librelane-chip` ซึ่งบันทึก `librelane.log`, `result.json`, `meta/librelane-chip.json` และคัดลอก final views

LibreLane `Chip` ใน 3.0.5 เพิ่ม pad ring, antenna check, seal ring, filler และ density ลงบน Classic flow ที่รวม extraction/STA/DRC/LVS โดยขั้นที่ enabled จริงขึ้นกับ config และ PDK ต้องอ่านรายการ step ที่รันจริง ห้ามนับ skipped step ว่า pass

**Gate หลังจบ:**

- คำสั่ง exit 0 และ `result.json` มี `status=passed`, `exit_code=0`
- final GDS/GDS.GZ มีข้อมูลจริง, top cell ถูกต้อง, macro/pad/bondpad views ครบ
- DRC/LVS/antenna/density และ timing reports อ้างถึง run/PDK revision เดียวกัน
- รายงาน WNS/TNS และ hold violations ตามทุก corner/scenario ที่กำหนด ไม่เลือกเฉพาะ typical
- เปิด layout ตรวจ chip outline, orientation, SRAM, pad ring, bondpads, seal ring และ power network

อย่าใส่ `--skip KLayout.DRC` หรือ `--skip Magic.DRC` ใน baseline นี้แล้วเรียกผลนั้นว่า “ผ่าน full-chip verification” ถ้ามีข้อจำกัดของ deck ต้องบันทึกว่าไม่ได้ตรวจและระบุ scope ของผล GDS

### วิธีค้นรายงานโดยไม่เดา step number

เมื่อกำหนด `VARIANT_ROOT` ตามขั้น 7 แล้ว:

```bash
export CHIP_RUN="$VARIANT_ROOT/physical/librelane/mini/chip"
find "$CHIP_RUN/runs/full01" -type f \
  \( -name '*.rpt' -o -name '*metrics*.json' -o -name '*lvs*' -o -name '*drc*' \) -print
cat "$CHIP_RUN/result.json"
```

ใช้ชื่อ step และ path จริงจาก run directory เพราะเลขลำดับ step เปลี่ยนได้ตาม gating/substitution

## 14. Package โดยไม่รัน P&R ซ้ำ

```bash
python3 scripts/run_fullchip.py \
  --repo "$RETROSOC_ROOT" \
  --librelane-python "/absolute/path/to/librelane-3.0.5/bin/python" \
  --run-tag full01 --stages package
```

runner ตรวจ successful result, tag ที่บันทึก และ final GDS ก่อนเรียก package script โดยตรง ได้ archive ที่:

```text
<VARIANT_ROOT>/physical/librelane/mini/chip/retrosoc-ihp130-chip-full01.tar.gz
```

ข้างในประกอบด้วย `final/`, `evidence/run/`, config, result, manifest, doctor result, dependency lock และ `SHA256SUMS`

ตรวจ archive หลังแตกใน directory ใหม่:

```bash
mkdir -p "$HOME/workshop/retrosoc-delivery-check"
tar -xzf "$CHIP_RUN/retrosoc-ihp130-chip-full01.tar.gz" \
  -C "$HOME/workshop/retrosoc-delivery-check"
cd "$HOME/workshop/retrosoc-delivery-check/retrosoc-ihp130-chip"
sha256sum -c SHA256SUMS
```

การผ่าน checksum พิสูจน์ integrity ของ archive เท่านั้น การรับมอบชิปต้องตรวจ report gates ในขั้น 13 ด้วย ชุด pad ring เป็น bare-die plan ยังไม่ใช่ package pinout/bond plan ที่ผ่าน electrical/ESD review

## 15. Debugging ตามอาการ

| อาการ | ตรวจที่ใดก่อน | การแก้ที่เหมาะสม |
|---|---|---|
| `Failed to calculate build variant ID` | `scripts/config_key.py --help`, Python/lock | ตรวจว่าใช้ source snapshot นี้และ interpreter ตาม baseline |
| หา `rtl/mini` หรือ filelists ไม่พบ | working directory, managed setup, generator outputs | รันจาก repo root ใช้ profile/BUILD_TIMESTAMP เดิม; รัน setup ที่เกี่ยวข้อง |
| หา `librelane` ไม่พบ | `command -v librelane`, regression DEFAULT_TOOLS | เข้า LibreLane 3.0.5 environment แยก |
| doctor หา PDK config ไม่พบ | `physical/pdk/IHP-Open-PDK/ihp-sg13g2/...` | ตรวจ manual-PDK root ต้องเป็น parent ของ `ihp-sg13g2` |
| unknown configuration key | LibreLane version / PDK config revision | ใช้ baseline ให้ตรงก่อน migration |
| `Unmapped Yosys instances` | synthesis netlist และ log รอบ unmapped cell | ตรวจ missing modules, unsupported construct, SRAM blackbox/cell views |
| `CheckMacroInstances` | generated MACROS และ post-synth names | ตรวจ hierarchy/flatten behavior ไม่เดาชื่อใหม่ |
| SDC required pin missing | flattened instance names ของ clock buffers/pads | ตรวจ actual synthesized netlist และ source generator |
| SRAM power unconnected | macro pin names ทั้ง LEF/CDL และ PDN reports | แยกตรวจ VDDARRAY!/VDD!/VSS! และ via connectivity |
| invalid routing layer | PDK layer names / PDN config | ใช้ชื่อ IHP เช่น Metal5/TopMetal1 ตาม view จริง |
| package หา run tag ไม่พบ | `LIBRELANE_RUN_TAG` ไม่ตรงกับ run ที่สำเร็จ | ใช้ `--run-tag` ให้ตรง directory ใต้ `runs/` |
| package เริ่มรัน chip ใหม่ | ใช้ Make target แทน runner package stage | ใช้ `python3 scripts/run_fullchip.py --stages package` หลัง validate |
| มี GDS แต่ไม่มี LVS report | executed/skipped step list | ผลยังไม่ครบ; รัน verification และ review scope |

## 16. Validation record และการรับมอบ

ดู `REVIEW-STATUS.md` ใน kit สำหรับผลที่รันจริง ข้อจำกัดของเครื่องตรวจครั้งนี้คือ Python ปัจจุบันไม่มี `pytest`/`ruff` environment ตาม lock และไม่มี LibreLane/OpenROAD/Yosys/Verilator/Icarus พร้อม managed dependencies ครบ จึงไม่มี full-chip result หรือ PPA ที่วัดจริง

| รายการ | สถานะ 30 กันยายน 2026 | ความหมาย |
|---|---|---|
| Baseline/HEAD | ผ่าน | upstream `main` และ checkout ตรง `7a58375...` |
| Source changes | ผ่าน static checks | `git diff --check`, Python compile และ targeted tests ผ่าน |
| `config_key.py --help` | ผ่าน | แก้ argparse `%Y` แล้ว |
| Package non-current tag | ผ่าน self-test | fixture ยืนยัน `reviewed-run` ถูกบรรจุ และ Make dry-run ไม่เรียก chip ซ้ำ |
| `ruff` / `pytest` | ยังไม่รัน | ต้องเปิด locked development environment |
| Functional regression | ยังไม่รัน | ต้องมี managed dependencies/toolchains |
| LibreLane doctor/chip | ยังไม่รัน | ต้องมี LibreLane 3.0.5 และ IHP PDK checkout ที่ pin |
| Signoff/physical review | ยังไม่รัน | ต้องตรวจ reports/layout จริงและ qualified decks |

ก่อนใช้เป็น teaching lab ที่ประกาศ ready-to-run end-to-end ให้เก็บหลักฐานบนเครื่อง workshop อย่างน้อย:

| Gate | หลักฐานที่ต้องเก็บ |
|---|---|
| Setup | OS/Python/tool versions, lock digest, managed revisions |
| Python/build changes | `ruff check .`, `python3 -m pytest -q`, diff check |
| Functional | affected firmware build, simulator result และ success marker |
| Synthesis | no unmapped cells, macro/pad inventory, synthesis warnings |
| Physical | PDN connectivity, placement/route reports และหลักฐานว่า CTS ยัง disabled |
| Timing | extracted STA corners/modes, exceptions/unconstrained review |
| Verification | executed DRC/LVS/antenna/density reports |
| Delivery | final views, manifest และ SHA256SUMS |

คำสั่ง gate ของ repository ที่ยังต้องรันใน provisioned environment:

```bash
cd "$RETROSOC_ROOT"
ruff check .
python3 -m pytest -q
git diff --check
make regress-pr
```

`make regress-pr` มีขอบเขตหลาย PDK ต้อง setup-regression ให้ครบก่อน จึงควรแยกจาก IHP-only implementation acceptance ในคู่มือนี้

### Milestone ที่มีลำดับความสำคัญสูงสุด

1. Provision Ubuntu 22.04/Python 3.10 แล้วให้ `development_environment.py check`, `ruff` และ `pytest` ผ่าน
2. ให้ topology gates, Verilator `ci_smoke`, Icarus assembly, Yosys, netlist simulation และ OpenSTA ผ่านด้วย `BUILD_TIMESTAMP` เดียว
3. ติดตั้ง LibreLane 3.0.5 แบบแยก environment แล้วให้ `librelane-doctor` ผ่าน โดยยืนยัน PDK revision และ pad count 192
4. รัน Chip tag ใหม่หนึ่งครั้ง เก็บ `result.json`, run database, final views และ reports โดยไม่ package/re-run ทับ
5. ปิด hierarchy/SDC/PDN/DRC/LVS/antenna/timing review จากหลักฐานจริง ก่อนสร้าง delivery archive
6. ทำ package/bond/ESD/foundry-deck review แยกจาก open-source flow ก่อนใช้คำว่า tape-out ready

## 17. แหล่งอ้างอิงที่ตรวจ

- [RetroSoC baseline source](https://github.com/retroSoC/retroSoC/tree/7a58375c0bd7c24b98e36a5451288e0a0e5666dc)
- [Full-chip Makefile](https://github.com/retroSoC/retroSoC/blob/7a58375c0bd7c24b98e36a5451288e0a0e5666dc/physical/librelane/mini/Makefile)
- [Config generator](https://github.com/retroSoC/retroSoC/blob/7a58375c0bd7c24b98e36a5451288e0a0e5666dc/physical/librelane/mini/scripts/generate_chip_config.py)
- [SDC generator](https://github.com/retroSoC/retroSoC/blob/7a58375c0bd7c24b98e36a5451288e0a0e5666dc/physical/librelane/mini/scripts/generate_sdc.py)
- [Dependency lock](https://github.com/retroSoC/retroSoC/blob/7a58375c0bd7c24b98e36a5451288e0a0e5666dc/dependencies/dependencies.lock.json)
- [LibreLane 3.0.5 Chip flow](https://github.com/librelane/librelane/blob/3.0.5/librelane/flows/chip.py)
- [LibreLane 3.0.5 Classic steps](https://github.com/librelane/librelane/blob/3.0.5/librelane/flows/classic.py)
- [LibreLane Nix installation](https://github.com/librelane/librelane/blob/3.0.5/docs/source/installation/nix_installation/_common.md)
- [Pinned IHP IO configuration](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/970a7688e7dcce2a6172797df9ef47bde2f60f9f/ihp-sg13g2/libs.tech/librelane/sg13g2_io/config.tcl)
- [Pinned IHP SRAM LEF](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/970a7688e7dcce2a6172797df9ef47bde2f60f9f/ihp-sg13g2/libs.ref/sg13g2_sram/lef/RM_IHPSG13_1P_4096x16_c3_bm_bist.lef)
