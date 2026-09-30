"""Single source of truth for the badge electronics.

Every component is described once here (symbol, footprint, value, pin->net map).
gen_schematic.py turns this into a KiCad 9 schematic, gen_pcb.py into a PCB.
Coordinates for PCB placement are in mm, board frame = front view, origin at
top-left corner of the board, X right, Y down (KiCad convention).
"""
import os
import sys
from dataclasses import dataclass, field


def _kicad_share_dir():
    """Locate KiCad's share/kicad directory on Windows, macOS, or Linux."""
    env_keys = (
        "KICAD10_SYMBOL_DIR",
        "KICAD9_SYMBOL_DIR",
        "KICAD8_SYMBOL_DIR",
        "KICAD_SYMBOL_DIR",
    )
    for key in env_keys:
        val = os.environ.get(key)
        if val and os.path.isdir(val):
            return os.path.dirname(os.path.abspath(val))

    candidates = []
    if sys.platform.startswith("win"):
        roots = [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "KiCad"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "KiCad"),
        ]
        for kicad_root in roots:
            if os.path.isdir(kicad_root):
                for name in sorted(os.listdir(kicad_root), reverse=True):
                    candidates.append(os.path.join(kicad_root, name, "share", "kicad"))
        # Prefer 10.x (this machine's KiCad for ERC/DRC) then 9.x.
        ten = [c for c in candidates if os.path.sep + "10." in c or c.endswith(os.path.join("10.0", "share", "kicad"))]
        nine = [c for c in candidates if os.path.sep + "9." in c or c.endswith(os.path.join("9.0", "share", "kicad"))]
        if ten:
            candidates = ten + [c for c in candidates if c not in ten]
        elif nine:
            candidates = nine + [c for c in candidates if c not in nine]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
            os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport"),
        ]
    else:
        candidates = ["/usr/share/kicad", "/usr/local/share/kicad"]

    for share in candidates:
        if os.path.isdir(os.path.join(share, "symbols")) and os.path.isdir(os.path.join(share, "footprints")):
            return share
    return "/usr/share/kicad"


_KICAD_SHARE = _kicad_share_dir()
KICAD_SYM = os.path.join(_KICAD_SHARE, "symbols")
KICAD_FP = os.path.join(_KICAD_SHARE, "footprints")
PROJECT_FP = "lib"          # relative to hardware/pcb
ESPRESSIF_SYM = "lib/Espressif.kicad_sym"

# ----------------------------------------------------------------------------
# Board geometry
# ----------------------------------------------------------------------------
BOARD_W = 91.0
PANEL_H = 77.0            # e-paper panel outline 91 x 77, glued to the FRONT
STRIP_H = 7.0             # extra strip under the panel: USB-C mid-mount + buttons
BOARD_H = PANEL_H + STRIP_H
BOARD_CORNER_R = 2.0
# 嘉立创/JLCPCB 两层标准档 0.4/0.6/0.8/1.0/1.2/1.6/2.0，下单没有 0.75。
# TYPE-C-31-M-14 产品页写沉板 0.75 mm；0.8 mm 公差 ±0.1 → 实物 0.7–0.9，含 0.75。
# 2026-09-14 Wisdom：按 0.8 打样，不改座、不改板厚。改这个数会动过孔 4:1 和外壳 PCB_T。
BOARD_THICKNESS = 0.8
# GDEM042F86 spec 2026-06-17 p.6: outline 91.00 x 77.00 x 1.00, AA 84.80 x 63.60,
# L/R bezel 3.10, AA vertically centered so top/bottom bezel = (77-63.60)/2 = 6.70
PANEL_T = 1.0
ACTIVE_W, ACTIVE_H = 84.8, 63.6
ACTIVE_TOP = 6.7

# Zones on the BACK side (all components live on B.Cu)
BATTERY_POCKET = (3.0, 3.0, 50.0, 53.0)     # x0,y0,x1,y1 : keep free of parts & antenna
NFC_COIL_RECT = (53.0, 3.5, 88.0, 45.0)      # outer rectangle of the loop antenna
NFC_TURNS = 11
FPC_SLOT = (27.0, 77.6, 57.0, 79.6)        # slot for the panel FPC to pass to the back
ESP_ANT_KEEPOUT = (53.0, 60.0, 67.0, 76.0)  # no copper under/in front of the module antenna
NFC_TRACE_W = 0.5
NFC_TRACE_GAP = 0.5

# B.SilkS labels (text, x, y, size, thick). Keep clear of J1 (40,73) and SW1/SW2.
# BOOT/RST sit on the buttons; title/chipset sit above them, left of J1.
# Board silk min height is 0.8 mm (DRC text_height); do not go below.
SILK_BACK = [
    ("EPD 24P FPC  (panel on front side)", 43.0, 66.6, 0.8, 0.12),
    ("ESP32-C3 antenna keepout", 60.0, 73.5, 0.8, 0.12),
    ("BADGE-42C v0.1", 15.5, 67.5, 1.2, 0.2),
    ("ESP32-C3 + ST25DV64KC + 4.2\" BWRY", 15.5, 69.6, 0.8, 0.12),
    ("RST", 14.0, 77.6, 0.8, 0.12),
    ("BOOT", 22.5, 77.6, 0.8, 0.12),
    ("CHG", 86.5, 83.2, 0.8, 0.12),
    ("STAT", 65.0, 83.2, 0.8, 0.12),
    ("J2-1 VBAT", 4.5, 54.6, 0.8, 0.12),
]
# Extra B.Silk reference offsets after flip, mm (used when SILK_REF_XY has no entry).
SILK_REF_OFFSET = {
    "Q2": (0.0, -1.2),
    "Q1": (0.0, -1.1),
}
# Absolute B.Silk reference positions, mm. Prefer this over OFFSET so live-board
# updates and gen_pcb land on the same readable spot (H2 silk warnings).
SILK_REF_XY = {
    # NFC 0402 位号放到焊盘南侧并错开，避免互叠和压焊盘。
    "R11": (78.40, 53.85),
    "R12": (82.00, 54.55),
    "R13": (85.80, 53.85),
    # C8/R7 挪进电池仓空地，躲开 U1 左边框丝印和自身焊盘。
    "C8": (47.80, 47.20),
    "R7": (47.80, 50.40),
    # C9 放到线圈下沿与零件之间，躲开 ANT1 位号。
    "C9": (68.50, 46.10),
    # R14 夹在 0603 与 C18 之间；R15 进仓内，躲开 D1。
    "R14": (24.50, 62.85),
    "R15": (29.80, 51.10),
    "C18": (24.50, 66.40),
    "D2": (33.50, 62.70),
    "D3": (38.70, 62.80),
}

# Locked first-article battery (F17, 2026-09-15 Wisdom: no dual P/N, no missing cell).
# 202545: 20 x 25 x 45 mm class, thickness 2.0 mm, ~250 mAh, must include PCM.
# J2 pin 1 = VBAT (red), pin 2 = GND (black). USB without battery: charging LED/USB
# enumerate may fail; that is allowed and must be logged, not treated as a pass.
BATTERY = {
    "form": "202545",
    "chemistry": "LiPo",
    "nominal_v": 3.7,
    "capacity_mah": 250,
    "thickness_mm": 2.0,
    "pcm": True,
    "j2_pin1": "VBAT",
    "j2_pin2": "GND",
}

# ----------------------------------------------------------------------------
# Component model
# ----------------------------------------------------------------------------
@dataclass
class Part:
    ref: str
    lib: str                 # symbol library nickname
    symbol: str              # symbol name inside that library
    footprint: str           # "LibNick:FootprintName"
    value: str
    pins: dict               # pin number -> net name
    nc: list = field(default_factory=list)   # pin numbers intentionally unconnected
    section: str = ""
    desc: str = ""           # BOM description / MPN hint
    lcsc: str = ""
    # PCB placement (x, y, rotation_deg). None -> placed in an overflow row
    at: tuple = None
    dnp: bool = False
    omit_pins: list = field(default_factory=list)  # symbol pins with no footprint pad


def exclude_from_bom(part):
    return bool(part.dnp or part.ref == "ANT1" or part.ref.startswith("TP"))


def board_footprint_id(part):
    """FPID written on the live board / schematic Footprint field."""
    return part.footprint


def nc_unconnected_net(ref, pad_number):
    """KiCad schematic-parity net name for an intentional no-connect pad."""
    if ref == "J1":
        pin = f"Pin_{pad_number}"
    elif ref == "J3":
        pin = {"A8": "SBU1", "B8": "SBU2", "SH": "SH", "S1": "SH"}.get(pad_number, pad_number)
    elif ref in ("U1", "U4"):
        pin = "NC"
    else:
        pin = pad_number
    return f"unconnected-({ref}-{pin}-Pad{pad_number})"


def R(ref, value, n1, n2, at=None, fp="Resistor_SMD:R_0402_1005Metric", section="", desc="", dnp=False):
    return Part(ref, "Device", "R", fp, value, {"1": n1, "2": n2}, section=section, desc=desc or f"{value} 0402 1%", at=at, dnp=dnp)


def C(ref, value, n1, n2, at=None, fp="Capacitor_SMD:C_0402_1005Metric", section="", desc="", dnp=False):
    return Part(ref, "Device", "C", fp, value, {"1": n1, "2": n2}, section=section, desc=desc or f"{value} 0402", at=at, dnp=dnp)


C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"

PARTS = [
    # ------------------------------------------------------------------ USB-C
    Part("J3", "Connector", "USB_C_Receptacle_USB2.0_16P", "badge:TYPE-C-31-M-14",
         "USB-C 16P 沉板 (TYPE-C-31-M-14)",
         {"A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "SH": "GND",
          "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
          "A5": "CC1", "B5": "CC2",
          "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN"},
         nc=["A8", "B8"], section="USB", desc="HRO TYPE-C-31-M-14, 16P USB 2.0 mid-mount receptacle", lcsc="C223907",
         at=(75.0, BOARD_H - 2.7, 0)),
    R("R1", "5.1k", "CC1", "GND", at=(67.5, 78.5, 90), section="USB"),
    R("R2", "5.1k", "CC2", "GND", at=(83.0, 78.5, 90), section="USB"),
    C("C1", "4.7u", "VBUS", "GND", at=(87.5, 72.0, 90), fp=C0603, section="USB", desc="4.7uF 10V X5R 0603"),

    # ------------------------------------------------------- Charger + battery
    Part("U3", "Battery_Management", "MCP73831-2-OT", "Package_TO_SOT_SMD:SOT-23-5",
         "TP4054",
         {"1": "CHRG_STAT", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"},
         section="POWER", desc="TP4054 Li-ion linear charger 4.2V SOT-23-5; R3=5.1k -> ~200mA. Not MCP73831.",
         lcsc="C32574", at=(80.0, 70.0, 0)),
    R("R3", "5.1k", "PROG", "GND", at=(76.5, 72.5, 0), section="POWER", desc="5.1k -> ~200mA charge current"),
    R("R4", "1k", "VBUS", "LED_CHRG_A", at=(86.5, 77.5, 90), section="POWER"),
    Part("D4", "Device", "LED", "LED_SMD:LED_0603_1608Metric", "RED",
         {"1": "CHRG_STAT", "2": "LED_CHRG_A"}, section="POWER", desc="LED 0603 red, charging indicator",
         at=(86.5, 81.0, 0)),
    C("C2", "4.7u", "VBAT", "GND", at=(83.5, 73.5, 0), fp=C0603, section="POWER", desc="4.7uF 10V X5R 0603"),
    Part("J2", "Connector_Generic", "Conn_01x02", "badge:JST_SHL_SM02B-SHLS-TF_1x02-1MP_P1.00mm_Horizontal",
         "BATT JST-SHL 1.0mm", {"1": "VBAT", "2": "GND"}, section="POWER",
         desc="JST SM02B-SHLS-TF 1.0mm 2P; pin1=VBAT red, pin2=GND; cell 202545 250mAh 2.0mm with PCM",
         lcsc="C145956", at=(10.0, 58.0, 0)),

    # ----------------------------------------------------------------- LDO 3V3
    Part("U4", "Regulator_Linear", "AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5", "XC6220B331MR-G",
         {"1": "VBAT", "2": "GND", "3": "VBAT", "5": "+3V3"}, nc=["4"], section="POWER",
         desc="LDO 3.3V Iq 8uA 1A SOT-25 VIN/GND/CE/NC/VOUT. Torex 3.0-3.5V pair: CIN=10uF CL=4.7uF near U4.",
         lcsc="C86534", at=(74.0, 66.5, 0)),
    C("C3", "10u", "VBAT", "GND", at=(70.5, 66.5, 90), fp=C0603, section="POWER",
      desc="10uF 6.3V X5R 0603 LDO CIN (Torex table, 3.3V with CL=4.7uF)"),
    C("C4", "4.7u", "+3V3", "GND", at=(77.5, 63.5, 0), fp=C0603, section="POWER",
      desc="4.7uF 10V X5R 0603 LDO CL near VOUT (Torex 3.00-3.50V + CIN=10uF)"),
    # battery voltage sense divider (2uA standby)
    R("R5", "1M", "VBAT", "BAT_SENSE", at=(70.0, 60.5, 0), section="POWER"),
    R("R6", "1M", "BAT_SENSE", "GND", at=(73.0, 60.5, 0), section="POWER"),
    C("C5", "100n", "BAT_SENSE", "GND", at=(76.0, 60.5, 0), section="POWER"),
    Part("TP4", "Connector", "TestPoint", "TestPoint:TestPoint_Pad_D1.0mm", "VBAT", {"1": "VBAT"},
         section="POWER", desc="test pad", at=(5.0, 62.0, 0)),
    Part("TP2", "Connector", "TestPoint", "TestPoint:TestPoint_Pad_D1.0mm", "3V3", {"1": "+3V3"},
         section="POWER", desc="test pad", at=(5.0, 65.0, 0)),
    Part("TP3", "Connector", "TestPoint", "TestPoint:TestPoint_Pad_D1.0mm", "GND", {"1": "GND"},
         section="POWER", desc="test pad", at=(5.0, 68.0, 0)),

    # --------------------------------------------------------------------- MCU
    Part("U1", "Espressif", "ESP32-C3-MINI-1", "badge:ESP32-C3-MINI-1", "ESP32-C3-MINI-1-N4",
         {**{str(p): "GND" for p in [1, 2, 11, 14] + list(range(36, 54))},
          "3": "+3V3", "8": "EN",
          "12": "BAT_SENSE",      # GPIO0 / ADC1_CH0
          "13": "NFC_GPO",        # GPIO1  (RTC wake)
          "5": "EPD_PWR_EN",      # GPIO2  strapping: pulled high, P-MOS off by default
          "6": "EPD_BUSY",        # GPIO3
          "18": "I2C_SDA",        # GPIO4
          "19": "I2C_SCL",        # GPIO5
          "20": "EPD_SCK",        # GPIO6
          "21": "EPD_MOSI",       # GPIO7
          "22": "LED_STAT_n",     # GPIO8  strapping: LED sink, idles high
          "23": "BOOT_n",         # GPIO9  strapping: boot button / user button
          "16": "EPD_CS",         # GPIO10
          "26": "USB_DN",         # GPIO18
          "27": "USB_DP",         # GPIO19
          "30": "EPD_DC",         # GPIO20
          "31": "EPD_RST"},       # GPIO21
         nc=[str(p) for p in [4, 7, 9, 10, 15, 17, 24, 25, 28, 29, 32, 33, 34, 35]],
         section="MCU", desc="Espressif ESP32-C3-MINI-1-N4 Wi-Fi/BLE module, 13.2x16.6x2.4mm", lcsc="C2934569",
         at=(60.0, 57.0, 180)),
    C("C6", "10u", "+3V3", "GND", at=(51.5, 56.6, 90), fp=C0603, section="MCU", desc="10uF 6.3V X5R 0603"),
    C("C7", "100n", "+3V3", "GND", at=(51.5, 54.0, 90), section="MCU"),
    R("R7", "10k", "+3V3", "EN", at=(51.5, 51.4, 90), section="MCU"),
    C("C8", "1u", "EN", "GND", at=(51.5, 48.8, 90), section="MCU"),
    R("R8", "10k", "+3V3", "BOOT_n", at=(69.0, 54.0, 90), section="MCU"),
    R("R10", "10k", "+3V3", "EPD_PWR_EN", at=(69.0, 56.8, 90), section="MCU"),
    R("R9", "1k", "+3V3", "LED_STAT_A", at=(65.0, 78.0, 0), section="MCU"),
    Part("D5", "Device", "LED", "LED_SMD:LED_0603_1608Metric", "GREEN",
         {"1": "LED_STAT_n", "2": "LED_STAT_A"}, section="MCU", desc="LED 0603 green, status", at=(65.0, 81.0, 0)),
    Part("SW1", "Switch", "SW_Push", "Button_Switch_SMD:SW_SPST_PTS810", "RESET",
         {"1": "EN", "2": "GND"}, section="MCU", desc="C&K PTS810 low-profile tactile 1.5mm", lcsc="C221929",
         at=(14.0, BOARD_H - 3.5, 0)),
    Part("SW2", "Switch", "SW_Push", "Button_Switch_SMD:SW_SPST_PTS810", "BOOT/USER",
         {"1": "BOOT_n", "2": "GND"}, section="MCU", desc="C&K PTS810 low-profile tactile 1.5mm", lcsc="C221929",
         at=(22.5, BOARD_H - 3.5, 0)),

    # --------------------------------------------------------------------- NFC
    Part("U2", "Badge", "ST25DV64KC-SO8N", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "ST25DV64KC-IER6S3",
         {"1": "NFC_VEH", "2": "NFC_AC0", "3": "NFC_AC1", "4": "GND", "5": "I2C_SDA", "6": "I2C_SCL",
          "7": "NFC_GPO", "8": "+3V3"}, section="NFC",
         desc="ST25DV64KC dynamic NFC tag, 64Kbit, FTM mailbox, energy harvesting, SO8N", lcsc="C2830253",
         at=(74.0, 51.5, 0)),
    C("C9", "100n", "+3V3", "GND", at=(68.5, 49.0, 90), section="NFC"),
    C("C10", "1u", "NFC_VEH", "GND", at=(68.5, 51.4, 90), section="NFC"),
    Part("TP1", "Connector", "TestPoint", "TestPoint:TestPoint_Pad_D1.0mm", "V_EH", {"1": "NFC_VEH"},
         section="NFC", desc="test pad (energy harvesting output)", at=(87.5, 49.6, 0)),
    R("R11", "4.7k", "+3V3", "I2C_SDA", at=(80.0, 51.5, 90), section="NFC"),
    R("R12", "4.7k", "+3V3", "I2C_SCL", at=(82.0, 51.5, 90), section="NFC"),
    R("R13", "100k", "+3V3", "NFC_GPO", at=(84.0, 51.5, 90), section="NFC"),
    Part("ANT1", "Device", "Antenna_Loop", "badge:NFC_Loop", "PCB loop 35x41.5mm 11T",
         {"1": "NFC_AC0", "2": "NFC_AC1"}, section="NFC",
         desc="PCB spiral antenna, net-tie footprint generated by gen_nfc_footprint.py; tune with C11",
         at=((NFC_COIL_RECT[0] + NFC_COIL_RECT[2]) / 2, (NFC_COIL_RECT[1] + NFC_COIL_RECT[3]) / 2, 0)),
    C("C11", "DNP", "NFC_AC0", "NFC_AC1", at=(82.5, 48.9, 0), section="NFC",
      desc="antenna tuning cap (fit after measuring resonance; ST25DV has 28.5pF internal)", dnp=True),

    # ------------------------------------------------------------------ E-PAPER
    Part("J1", "Connector_Generic", "Conn_01x24", "Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal",
         "EPD FPC 24P 0.5mm",
         {"2": "EPD_GDR", "3": "EPD_RESE", "5": "EPD_VSH2", "8": "GND",
          "9": "EPD_BUSY", "10": "EPD_RST", "11": "EPD_DC", "12": "EPD_CS", "13": "EPD_SCK", "14": "EPD_MOSI",
          "15": "EPD_VCI", "16": "EPD_VCI", "17": "GND", "18": "EPD_VDD",
          "20": "EPD_VSH1", "21": "EPD_VGH", "22": "EPD_VSL", "23": "EPD_VGL", "24": "EPD_VCOM"},
         nc=["1", "4", "6", "7", "19"], section="EPD",
         desc="24P 0.5mm FPC connector, bottom contact, flip lock (Hirose FH12-24S-0.5SH or JUSHUO AFC07-S24FCA-00). Pin 7 NC Keep Open (GDEM042F86 p.7).",
         lcsc="C262657", at=(40.0, 73.0, 0)),
    Part("Q2", "Transistor_FET", "AO3401A", "Package_TO_SOT_SMD:SOT-23", "AO3401A",
         {"1": "EPD_PWR_EN", "2": "+3V3", "3": "EPD_VCI"}, section="EPD",
         desc="P-MOSFET load switch for panel + boost", lcsc="C15127", at=(38.5, 57.5, 0)),
    C("C12", "10u", "EPD_VCI", "GND", at=(42.5, 57.5, 0), fp=C0603, section="EPD", desc="10uF 6.3V X5R 0603"),
    C("C13", "1u", "EPD_VCI", "GND", at=(45.5, 57.5, 0), section="EPD"),
    C("C14", "1u", "EPD_VDD", "GND", at=(42.0, 64.5, 0), section="EPD"),
    Part("L1", "Device", "L", "Inductor_SMD:L_Changjiang_FNR4018S", "47uH",
         {"1": "EPD_VCI", "2": "EPD_SW"}, section="EPD",
         desc="47uH shielded, Isat 700mA Irms 650mA, 4.0x4.0x1.8mm FNR4018S470MT (GDEM042F86 p.29 47uH/500mA)",
         lcsc="C167813", at=(24.5, 57.5, 0)),
    Part("Q1", "Transistor_FET", "AO3400A", "badge:SOT-323_SC-70", "Si1308EDL",
         {"1": "EPD_GDR", "2": "EPD_RESE", "3": "EPD_SW"}, section="EPD",
         desc="Vishay Si1308EDL-T1-GE3 N-MOS 30V SOT-323 GSD (GDEM042F86 p.29). Symbol AO3400A is pin-compatible GSD.",
         lcsc="C469327", at=(29.0, 57.5, 0)),
    R("R14", "2.2R", "EPD_RESE", "GND", at=(24.5, 61.0, 0), fp="Resistor_SMD:R_0603_1608Metric", section="EPD",
      desc="RESE 2.2 ohm 0603 >=0.1W (GDEM042F86 p.29; 0402 pulse rating not locked)"),
    R("R15", "1M", "EPD_GDR", "GND", at=(32.5, 54.5, 0), section="EPD",
      desc="GDR 1M pulldown to GND (GDEM042F86 p.29 R1)"),
    Part("D1", "Diode", "MBR0530", "Diode_SMD:D_SOD-123", "MBR0530",
         {"1": "EPD_VGH", "2": "EPD_SW"}, section="EPD", desc="Schottky 30V 0.5A SOD-123", lcsc="C77896", at=(33.5, 57.5, 0)),
    C("C15", "4.7u/25V", "EPD_SW", "EPD_PUMP", at=(29.0, 61.0, 0), fp=C0805, section="EPD",
      desc="4.7uF 25V X5R 0805 flying cap (GDEM042F86 p.29 C3)"),
    Part("D2", "Diode", "MBR0530", "Diode_SMD:D_SOD-123", "MBR0530",
         {"1": "GND", "2": "EPD_PUMP"}, section="EPD", desc="Schottky 30V 0.5A SOD-123", lcsc="C77896", at=(33.5, 61.0, 0)),
    Part("D3", "Diode", "MBR0530", "Diode_SMD:D_SOD-123", "MBR0530",
         {"1": "EPD_PUMP", "2": "EPD_VGL"}, section="EPD", desc="Schottky 30V 0.5A SOD-123", lcsc="C77896", at=(38.7, 61.0, 0)),
    C("C16", "1u/50V", "EPD_VGH", "GND", at=(43.0, 61.0, 0), fp=C0805, section="EPD", desc="1uF 50V X7R 0805"),
    C("C17", "1u/50V", "EPD_VGL", "GND", at=(46.8, 61.0, 0), fp=C0805, section="EPD", desc="1uF 50V X7R 0805"),
    C("C18", "1u/25V", "EPD_VSH1", "GND", at=(24.5, 64.5, 0), fp=C0603, section="EPD", desc="1uF 25V X7R 0603"),
    C("C19", "1u/25V", "EPD_VSH2", "GND", at=(28.0, 64.5, 0), fp=C0603, section="EPD", desc="1uF 25V X7R 0603"),
    C("C20", "1u/25V", "EPD_VSL", "GND", at=(31.5, 64.5, 0), fp=C0603, section="EPD", desc="1uF 25V X7R 0603"),
    C("C21", "1u/25V", "EPD_VCOM", "GND", at=(35.0, 64.5, 0), fp=C0603, section="EPD", desc="1uF 25V X7R 0603"),
]

# Nets that need a PWR_FLAG for ERC (no power-output pin drives them)
PWR_FLAG_NETS = ["GND", "VBUS"]

# Net classes: track/clearance are DRC-mandatory minima (F05, 2026-09-15).
# Preferred width equals the minimum. Existing 0.15/0.2 mm Power/NFC segments are non-compliant
# and must be re-routed; do not claim the board meets these classes until DRC says so.
NET_CLASSES = {
    "Default": {"clearance": 0.15, "track": 0.2, "via": 0.6, "via_drill": 0.3, "nets": []},
    "Power": {"clearance": 0.2, "track": 0.3, "via": 0.6, "via_drill": 0.3,
              "nets": ["GND", "VBUS", "VBAT", "+3V3", "EPD_VCI", "EPD_SW", "EPD_RESE"]},
    "NFC": {"clearance": 0.3, "track": 0.5, "via": 0.6, "via_drill": 0.3, "nets": ["NFC_AC0", "NFC_AC1"]},
}

SECTION_NOTES = {
    "USB": "USB-C 2.0, mid-mount receptacle in the 7mm strip below the panel. CC pulled down 5.1k = UFP. D+/D- go straight to the ESP32-C3 native USB.",
    "POWER": "LiPo 202545 250mAh 2.0mm with PCM, J2-1=VBAT. TP4054 ~200mA. XC6220 near-end CIN=10uF CL=4.7uF. Standby current is unmeasured; do not quote 13uA or two years.",
    "MCU": "ESP32-C3-MINI-1. Strapping pins: GPIO2 pulled high (P-MOS off at boot), GPIO8 LED sink (idles high), GPIO9 boot/user button. No UART bridge: program/log over native USB.",
    "NFC": "ST25DV64KC: NDEF URL + fast-transfer mailbox (256B) + RF field wake on GPO -> GPIO1. Loop antenna is drawn on B.Cu in gen_pcb.py; internal tuning cap 28.5pF, target L ~4.8uH; C11 is a DNP trim cap.",
    "EPD": "4.2\" BWRY GDEM042F86. Boost per p.29: 47uH/500mA-class (FNR4018S470MT 700mA Isat), Si1308EDL, 4.7uF flying cap, GDR 1M to GND, RESE 2.2R 0603. Pin 7 NC Keep Open (p.7). BS1=GND -> 4-wire SPI. Panel power gated by Q2.",
}


def all_nets():
    nets = {}
    for p in PARTS:
        for pin, net in p.pins.items():
            nets.setdefault(net, []).append((p.ref, pin))
    return nets


if __name__ == "__main__":
    nets = all_nets()
    print(f"{len(PARTS)} parts, {len(nets)} nets")
    for n, pins in sorted(nets.items()):
        print(f"{n:14s} {len(pins):2d}  {' '.join(f'{r}.{p}' for r, p in pins)}")

# 2026-09-30 NEW portrait mechanical study. Not an electrical migration of H2.
# User requested screen reselection, improved portrait dimensions and stability.
# This isolated dictionary DOES NOT change BOARD_W/PARTS/H2 generated outputs.
# All provisional fields are design envelopes, not approved footprints/BOM.
PORTRAIT = {
    "version": "P1.1-revisionB-11.1mm-not-for-manufacture",
    "board": {"w": 58.0, "h": 92.64, "t": 0.8, "provisional": True,
              "fpc_slot": [13.0, 88.0, 41.2, 89.4]},
    "panel": {
        "model": "Waveshare-3.6inch-e-Paper-HAT-Plus-panel", "x": 1.0, "y": 0,
        "w": 56.0, "h": 86.6, "t": 0.78, "t_max": 1.2,
        "active_x": 3.6, "active_y": 2.6, "active_w": 50.8,
        "active_h": 76.2, "window_rect": [3.3, 2.3, 54.7, 79.1],
        "provisional": True,
        "warning": "Nominal panel with film 0.78+/-0.07; conservative 1.2 local UV-glue envelope. 50-pin FPC bend and sample fit remain unverified",
    },
    "enclosure": {
        "outer_w": 66.0, "outer_h": 109.0, "top_extension": 9.0,
        "edge_clearance": 0.35, "bezel_t": 1.2, "panel_gasket": 0.2,
        "panel_adhesive": 0.10, "back_space": 6.2, "back_cover_t": 1.4,
        "native_revision": "revisionB", "bottom_right_screw_x": 37.0,
        "screw_length_mm": 10.0, "screw_blind_top_z": 2.7,
        "pcb_support_rects": [[1, 1, 3, 3], [55, 18, 57, 20],
                              [1, 89.64, 3, 91.64], [41.6, 90.14, 43.6, 92.14]],
        "service_buttons": [{"ref": "SW1", "label": "RESET", "x": 6.0, "y": 88.0, "hole_d": 2.4},
                            {"ref": "SW2", "label": "BOOT", "x": 7.5, "y": 83.5, "hole_d": 2.4}],
        "update_button": {"ref": "SW3", "x": 3.0, "y": 46.0,
                          "beam_w": 4.0, "beam_length": 13.0, "beam_t": 0.65,
                          "isolation_slot": 0.45, "tip_z": -2.8, "hard_stop_travel": 0.6,
                          "switch_nominal_h": 2.5, "switch_travel_nominal": 0.15,
                          "warning": "Integrated flexure concept, nominal0.3gap; print/height/boardclamp tolerance, returnforce, overtravel and fatigue require first-article tuning"},
    },
    "card": {
        "enabled": False,
        "status": "External removable card carrier cancelled by user; integrated credential space unresolved",
        "w": 54.0, "h": 85.6, "t": 0.76, "xy_clearance": 0.4,
        "slot_t": 1.35, "wall_t": 1.0, "top_y": 5.0,
    },
    "battery": {
        "model": "Adafruit 1578 protected 500mAh",
        "rect": [1.0, 4.5, 32.0, 42.5], "thickness": 5.1,
        "max_envelope_t": 5.6, "provisional": True,
        "warning": "31x38x5.6 is an engineering envelope, not supplier max or proven swelling allowance; original102mm leads remain uncut",
    },
    "wire_keepout": {"rect": [14.0, 44.0, 31.0, 50.5], "z_min": -6.0, "z_max": 0.0,
                     "warning": "Reserved volume only; full102mm loose leads and strain relief require physical fit"},
    "battery_plug_keepout": {"rect": [5.7, 43.0, 12.3, 51.0], "z_min": -5.8, "z_max": 0.0,
                             "warning": "PHR2 nominal5.8x6.85x4.5; mating position and lead exit remain physical-fit gates"},
    "fpc_keepout": {
        "rect": [13.0, 80.0, 41.2, 92.64], "z_min": -3.2,
        "z_max": 2.3, "provisional": True,
    },
    "usb": {
        "side": "bottom", "center": 50.0, "opening_width": 10.4,
        "z_min": -2.5, "z_max": 1.6, "provisional": True,
        "body_size": [8.94, 7.96, 2.86], "body_f_z_min": -0.85, "body_f_z_max": 2.01,
        "model_offset": [0.0, 0.75, 0.0], "position_uncertainty_mm": 0.04,
        "approach": {"rect": [42.5, 93.0, 57.5, 101.0], "z_min": -3.83, "z_max": 2.67,
                     "gauge_mm": [15.0, 6.5], "warning": "Clearance envelope only; select a smaller actual overmold including tolerance, not universal cable fit"},
    },
}

# New electrical design is isolated so H2 can always be reproduced unchanged.
# Reversible P36 changes start at PORTRAIT above; new circuits source below.
PORTRAIT_ELECTRICAL_SOURCE = "hardware/portrait/pcb/scripts/design.py"
