#!/usr/bin/env python3
"""Generate exact-MPN purchasing candidates; no KiCad or PCB regeneration."""
from pathlib import Path
import sys,importlib.util,hashlib,json,csv,io,shutil,datetime
sys.dont_write_bytecode=True
R=Path('/workspace/scratch/200245c5fbc3/chroma-badge'); P=R/'hardware/portrait/pcb'; O=R/'docs/portrait'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected=list(P.glob('*.kicad_pcb'))+list(P.glob('*.kicad_sch'))+list((P/'scripts').glob('*.py'))+[R/'hardware/pcb/scripts/design.py']
before={str(p.relative_to(R)):sha(p) for p in protected}
spec=importlib.util.spec_from_file_location('procurement_source',P/'scripts/design.py');D=importlib.util.module_from_spec(spec);sys.modules[spec.name]=D;spec.loader.exec_module(D)
assert 'pcbnew' not in sys.modules
assert len(D.PARTS)==81 and len({p.ref for p in D.PARTS})==81
# Explicit researched candidates, full suffixes retained. All require first article.
DATA='''J3|HRO|TYPE-C-31-M-14|LCSC C223907|SOURCE_SPECIFIED|USB|*|16P mid-mount;1A rating;0.75mm vendor PCB versus0.8 candidate requires fit test.|USB
R1 R2|YAGEO|RC0402FR-075K1L|DigiKey/Mouser exact MPN|CANDIDATE|R04|5.1k|1%,0.063W at70C,100ppm/K;independent CC pulldowns.|YAGEO
C1 C2 C4|TDK|C1608X5R1C475K080AC|TDK authorized distributor|CANDIDATE|C06|4.7u|4.7uF10%16V X5R;above10V source minimum;max body0.90mm;effective capacitance and LDO stability pending.|TDK
U3|Microchip|MCP73831T-2ACI/OT|Microchip Direct/DigiKey|SOURCE_SPECIFIED|S235|MCP73831T-2ACI/OT|4.2V charger;R3=10k nominal100mA;no cell-temperature input or safety timer.|CHARGER
R3 R7 R8 R10|YAGEO|RC0402FR-0710KL|DigiKey/Mouser exact MPN|CANDIDATE|R04|10k|1%,0.063W at70C,100ppm/K;R3 must remain10k.|YAGEO
R4 R9|YAGEO|RC0402FR-071KL|DigiKey/Mouser exact MPN|CANDIDATE|R04|1k|1%,0.063W at70C,100ppm/K;verify LED current.|YAGEO
D4|Kingbright|APT1608SURCK|DigiKey/Mouser exact MPN|CANDIDATE|LED06|RED|Red0603;nominal height0.75mm;check cathode and low-current visibility.|RED
J2|JST|S2B-PH-SM4-TB(LF)(SN)|DigiKey/Mouser;LCSC C295747|SOURCE_SPECIFIED|JST|*|PH2.0 horizontal;pin1GND,pin2VBAT;measure incoming keyed lead polarity;full mating fit pending.|JST
U4|Torex|XC6220B331MR-G|Torex Direct/DigiKey|SOURCE_SPECIFIED|S235|XC6220B331MR-G|3.3V;VIN/GND/CE/NC/VOUT;verify effective CIN/CL,dropout,load steps and temperature.|LDO
C3 C6|TDK|C1608X5R0J106K080AB|TDK authorized distributor|CANDIDATE|C06|10u|10uF10%6.3V X5R;max body0.90mm;VSYS transient/DC-bias checks pending.|TDK
R5 R6 R22|YAGEO|RC0402FR-071ML|DigiKey/Mouser exact MPN|CANDIDATE|R04|1M|1%,0.063W at70C,100ppm/K;divider leakage/calibration pending.|YAGEO
C5 C7 C101 C32|TDK|C1005X7R1C104K050BC|TDK authorized distributor|CANDIDATE|C04|100n|100nF10%16V X7R;max body0.55mm.|TDK
TP4 TP2 TP3|N/A|N/A|PCB fabrication artwork|FAB_ONLY|TP|*|Copper test pads only;purchase quantity0;no fitted hardware.|PCB
U1|Espressif|ESP32-C3-MINI-1-N4X|Espressif authorized distributor|SELECTED|ESP|ESP32-C3-MINI-1-N4X|Design-selected PCB antenna4MB module;no N4/MINI-1U substitution;on-body RF pending.|ESP
C8|Samsung Electro-Mechanics|CL05A105KP5NNNC|DigiKey/Mouser exact MPN|CANDIDATE|C04|1u|1uF10%10V X5R0402;max body0.55mm.|CAP1
D5|Kingbright|APT1608SGC|DigiKey/Mouser exact MPN|CANDIDATE|LED06|GREEN|Green0603;nominal height0.75mm;check actual approximately1mA visibility and cathode.|GREEN
SW1 SW2 SW3|C&K/Littelfuse|PTS810 SJM 250 SMTR LFS|DigiKey/Mouser exact MPN|CANDIDATE|SW|*|160gf;assembled2.5mm +0.2/-0.1;travel0.15+/-0.1mm;not old1.5mm;actuator first article pending.|SWITCH
Q10 Q20|Alpha and Omega Semiconductor|AO3401A|DigiKey/Mouser exact MPN|SOURCE_SPECIFIED|S23|AO3401A|P-MOS;G1/S2/D3;preserve load-share/gate orientation;inrush/leakage/heat pending.|PMOS
R20 R21|YAGEO|RC0402FR-07100KL|DigiKey/Mouser exact MPN|CANDIDATE|R04|100k|1%,0.063W at70C,100ppm/K.|YAGEO
D10|Vishay|SS14-E3/61T|DigiKey/Mouser exact MPN|CANDIDATE|SMA|SS14|40V1A SMA;K=VSYS,A=VBUS;forward drop and heat pending.|SMA
C30|TDK|C2012X5R1A226K125AB|TDK authorized distributor|CANDIDATE|C08|22u|22uF10%10V X5R;max body1.45mm;DC-bias/inrush pending.|TDK
J1|Hirose|FH34SRJ-50S-0.5SH(50)|DigiKey/Mouser exact MPN|SELECTED|FPC|*|Design-selected50P0.5 dual-contact for0.3mm FPC;nominal1.0mm height;pin1/locking/mating pending.|FPC
C100|Samsung Electro-Mechanics|CL32A107MQVNNNE|DigiKey/Mouser exact MPN|CANDIDATE|C1210|100u/6.3V|100uF20%6.3V X5R1210;max body2.8mm;bias/inrush/soldered height pending.|CAP100
FB1 FB2|Murata|BLM18PG121SN1D|DigiKey/Mouser exact MPN|REFERENCE_EXACT|L06|BLM18PG121SN1D|120ohm@100MHz;2A at datasheet conditions;DCRmax0.05ohm;bias/thermal pending.|FERRITE
L1 L2|cjiang/Changjiang|FNR4018S100MT|LCSC C167808|CANDIDATE|L4018|10uH|10uH20%,4x4x1.8mm,DCRmax0.234ohm;conservative Isat1.3A/Irms0.84A;typ1.6/1.2A not guaranteed;waveform/heat pending.|INDUCTOR
Q1|Alpha and Omega Semiconductor|AO3400A|DigiKey/Mouser exact MPN|CANDIDATE|S23|AO3400A|N-MOS G1/S2/D3;A differs from reference non-A;switching qualification pending.|NMOS
Q2|Vishay|SI2301CDS-T1-E3|DigiKey/Mouser exact MPN|REFERENCE_EXACT|S23|SI2301CDS-T1-E3|Negative-boost P-MOS G1/S2/D3;do not buy AO3401A from generic symbol name.|BOOST
R100 R102|YAGEO|RC0603FR-071ML|DigiKey/Mouser exact MPN|CANDIDATE|R06|1M|1%,0.1W at70C,100ppm/K;retain0603.|YAGEO
R101 R103|Panasonic|ERJ-6DSFR20V|DigiKey/element14 exact MPN|CANDIDATE|R08|0.2R|0.2ohm1%,0.5W@70C,TCR0..150ppm/K;5s overload test not repetitive boost-pulse approval;measure pulse/heat.|SENSE
R104|YAGEO|RC0603JR-070RL|DigiKey/Mouser exact MPN|CANDIDATE|R06|0R|Fitted0ohm0603 VPH/VGH link;verify jumper current/resistance.|YAGEO
D1 D2 D3 D6|onsemi|MBR0530T1G|DigiKey/Mouser exact MPN|CANDIDATE|SOD|MBR0530|30V0.5A SOD123;pin1K/pin2A;reverse/ripple/switching stress pending.|DIODE
C110 C114 C122|TDK|C2012X5R1E475K125AB|TDK authorized distributor|CANDIDATE|C08|4.7u/25V|4.7uF10%25V X5R;max body1.45mm;DC-bias/ripple pending.|TDK
C111 C129|TDK|C2012X7R1E474K125AA|TDK authorized distributor|CANDIDATE|C08|470n/25V|470nF10%25V X7R;max body1.45mm;rail stress pending.|TDK
C112 C113 C115 C116 C117 C118 C119 C120 C121 C125|TDK|C2012X5R1E106K125AB|TDK authorized distributor|CANDIDATE|C08|10u/25V|10uF10%25V X5R;max body1.45mm;effective capacitance/boost/flying-cap stress pending.|TDK
C123|TDK|C2012X7R1C225K125AB|TDK authorized distributor|CANDIDATE|C08|2.2u/6.3V|2.2uF10%16V X7R;above6.3V source minimum;max body1.45mm;VDDDO qualification pending.|TDK
C124 C126 C127 C128 C130 C131|TDK|C2012X7R1H105K125AB|TDK authorized distributor|CANDIDATE|C08|1u/50V|1uF10%50V X7R;max body1.45mm;retain50V;flying-cap bias/ripple pending.|TDK
U5|STMicroelectronics|USBLC6-2SC6|ST Direct/DigiKey|SOURCE_SPECIFIED|S236|USBLC6-2SC6|SOT23-6L;1/6IO1,2GND,3/4IO2,5VBUS;not2P6 package;component ESD rating is not badge certification.|ESD
R23|YAGEO|RC0402FR-07330KL|DigiKey/Mouser exact MPN|CANDIDATE|R04|330k|1%,0.063W at70C,100ppm/K;VBUS ADC calibration pending.|YAGEO'''
FP={'USB':'badge:TYPE-C-31-M-14','JST':'Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal','TP':'TestPoint:TestPoint_Pad_D1.0mm','ESP':'badge:ESP32-C3-MINI-1','SW':'Button_Switch_SMD:SW_SPST_PTS810','FPC':'badge:FH34SRJ-50S-0.5SH','L06':'Inductor_SMD:L_0603_1608Metric','L4018':'Inductor_SMD:L_Changjiang_FNR4018S','SMA':'Diode_SMD:D_SMA','SOD':'Diode_SMD:D_SOD-123','LED06':'LED_SMD:LED_0603_1608Metric'}
for k,n in [('R04','0402_1005'),('R06','0603_1608'),('R08','0805_2012')]:FP[k]='Resistor_SMD:R_'+n+'Metric'
for k,n in [('C04','0402_1005'),('C06','0603_1608'),('C08','0805_2012'),('C1210','1210_3225')]:FP[k]='Capacitor_SMD:C_'+n+'Metric'
for k,n in [('S23','SOT-23'),('S235','SOT-23-5'),('S236','SOT-23-6')]:FP[k]='Package_TO_SOT_SMD:'+n
URL={'USB':'https://www.lcsc.com/datasheet/C223907.pdf','CHARGER':'https://www.microchip.com/en-us/product/mcp73831','RED':'https://www.kingbrightusa.com/images/catalog/spec/apt1608surck.pdf','GREEN':'https://www.kingbrightusa.com/images/catalog/spec/apt1608sgc.pdf','JST':'https://www.jst-mfg.com/product/index.php?lang=2&series=153','LDO':'https://product.torexsemi.com/system/files/series/xc6220.pdf','ESP':'https://documentation.espressif.com/esp32-c3-mini-1_datasheet_en.html','CAP1':'https://product.samsungsem.com/mlcc/CL05A105KP5NNN.do','SWITCH':'https://www.ckswitches.com/media/2214/tactile.pdf','PMOS':'https://www.aosmd.com/res/data_sheets/AO3401A.pdf','SMA':'https://www.vishay.com/doc?88746=','FPC':'https://www.hirose.com/product/p/CL0580-1266-2-50','CAP100':'https://product.samsungsem.com/mlcc/CL32A107MQVNNN.do','FERRITE':'https://www.murata.com/products/productdata/8796738650142/ENFA0003.pdf?1730777412000=','INDUCTOR':'https://www.lcsc.com/product-detail/C167808.html ; https://img.ichunt.com/doc/pdf/cms/201807/19/de6ca674f8412d481b3fd051c98c9aff.pdf','NMOS':'https://www.aosmd.com/products/mosfets/low-voltage-mosfets-12v-30v/ao3400a','BOOST':'https://www.vishay.com/docs/68741/si2301cd.pdf','SENSE':'https://industrial.panasonic.com/cdbs/www-data/pdf/RDN0000/AOA0000C313.pdf','DIODE':'https://www.onsemi.com/download/data-sheet/pdf/mbr0530t1-d.pdf','ESD':'https://www.st.com/resource/en/datasheet/usblc6-2.pdf','PCB':'N/A: fabrication artwork'}
mapping={}
for line in DATA.splitlines():
 refs,maker,mpn,channel,status,fp,value,note,key=line.split('|')
 source=('https://yageogroup.com/component-documentation/download/specsheet/'+mpn) if key=='YAGEO' else ('https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no='+mpn) if key=='TDK' else URL[key]
 for ref in refs.split():
  assert ref not in mapping
  mapping[ref]=(maker,mpn,channel,status,FP[fp],value,note,source,key)
assert set(mapping)=={p.ref for p in D.PARTS}
base=[];rows=[]
for p in D.PARTS:
 maker,mpn,channel,status,fp,value,note,source,key=mapping[p.ref]
 assert p.footprint==fp,(p.ref,p.footprint,fp)
 assert value=='*' or p.value==value,(p.ref,p.value,value)
 fab=p.ref in {'TP2','TP3','TP4'};assert fab==(status=='FAB_ONLY')
 b=dict(Reference=p.ref,Value=p.value,Footprint=p.footprint,Description=p.desc,DNP=bool(getattr(p,'dnp',False)));base.append(b)
 rows.append(dict(b,Manufacturer=maker,ManufacturerMPN=mpn,ProcurementChannel=channel,EngineeringStatus=status,QualificationStatus='FABRICATION_FEATURE' if fab else 'FIRST_ARTICLE_PENDING',PurchaseQtyPerBoard=0 if fab or b['DNP'] else 1,ProcurementNotes=note,SourceURL=source,SourceNotes='Manufacturer data hosted by distributor; incoming revision must be verified' if key in {'USB','INDUCTOR'} else 'Manufacturer source; application qualification pending',ResearchDate='2026-09-30',StockVerified=False,PhysicalValidationComplete=False))
assert sum(r['PurchaseQtyPerBoard'] for r in rows)==78
assert {r['Reference'] for r in rows if r['PurchaseQtyPerBoard']==0}=={'TP2','TP3','TP4'}
off=[dict(Item='3.6inch E6 raw display',Manufacturer='Waveshare',ManufacturerMPN='32651',ProcurementChannel='Waveshare direct',PurchaseQtyPerBadge=1,SourceURL='https://www.waveshare.com/3.6inch-e-paper-hat-plus-e.htm?sku=32651',Notes='Vendor600x400 used portrait400x600;exact50pin panel;verify incoming FPC,marking and dimensions.'),dict(Item='Protected500mAh pack',Manufacturer='Adafruit',ManufacturerMPN='1578',ProcurementChannel='Adafruit direct',PurchaseQtyPerBadge=1,SourceURL='https://www.adafruit.com/product/1578',Notes='Original PH lead100-102mm retained;31x38x5.6 is engineering budget not supplier maximum or swelling allowance;incoming polarity/dimensions mandatory;100mA charge/500mA discharge delivered-pack and thermal qualification pending.'),dict(Item='NPTH holes and slots',Manufacturer='N/A',ManufacturerMPN='N/A',ProcurementChannel='PCB fabrication artwork',PurchaseQtyPerBadge=0,SourceURL='N/A',Notes='Fabrication features only;no fitted hardware implied.')]
for r in off:r.update(EngineeringStatus='FAB_ONLY' if r['PurchaseQtyPerBadge']==0 else 'SELECTED',QualificationStatus='FIRST_ARTICLE_PENDING' if r['PurchaseQtyPerBadge'] else 'FABRICATION_FEATURE',StockVerified=False,PhysicalValidationComplete=False,ResearchDate='2026-09-30')
def csvout(rows):
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);return s.getvalue()
text='''# P36 采购候选与询价清单

2026-09-30。81个PCB位号全部映射：78个装配位置，TP2/TP3/TP4三个制造测试焊盘采购数量为0。完整MPN、厂家、询价渠道、来源链接见 procurement_candidates.csv；屏和电池见 procurement_offboard_candidates.csv。数量不含损耗、备件、起订量。

SELECTED表示用户或受托工程选定，SOURCE_SPECIFIED表示电气源明确料号，REFERENCE_EXACT表示参考电路指定，CANDIDATE表示有来源的采购候选。全部装配件均待首件验证；未核现货、报价或交期，未下单。不能把本表直接当成贴片厂可替代料的生产BOM。

C1/C2/C4明确选16V替代原10V最低值，C123选16V替代原6.3V最低值。R101/R103为Panasonic ERJ-6DSFR20V，0.2欧1%0805，0.5W@70°C；5秒过载指标不是重复boost脉冲资格。Q2保持SI2301CDS-T1-E3，不按通用符号名误买AO3401A。SW1/2/3为2.5mm高度PTS810候选，不能沿用1.5mm旧描述。

采购前逐项核完整后缀、生命周期、封装、可追溯渠道和当前规格书；不接受仅容值或近似型号的静默替代。测量MLCC直流偏压后的有效电容、各高压轨峰值/纹波、电感峰值/RMS/饱和/温升、采样电阻脉冲、MOS和二极管应力。额定值不等于系统裕量已通过。

Adafruit1578的31×38×5.6mm是工程预算，非厂家保证最大值或老化膨胀保证。保留原配线并验证PH极性、批次尺寸及配对空间。两线电池无NTC，MCP73831只调节芯片温度，无电芯温度输入和安全计时器；原型须受控室温、监督充电和密闭壳温升验证。

机械胶带、PET、PORON、螺钉等见C1参数源与机械说明。当前PH预留与SW3、FPC预留与C118–121仍有装配阻断；采购候选表不消除这些冲突。门禁系统未知，不采购或承诺通用门禁模块。

本脚本只核数据覆盖、CSV读回和受保护源SHA不变，不调用KiCad/硬件生成器，不代表电气、热、RF或机械验收通过。
'''
outputs={P/'candidate_bom.csv':csvout(base),O/'procurement_candidates.csv':csvout(rows),O/'procurement_offboard_candidates.csv':csvout(off),O/'procurement_candidates.md':text}
assert all(p not in protected for p in outputs)
assert before=={str(p.relative_to(R)):sha(p) for p in protected}
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ');backup=O/'procurement_backups'/stamp;backup.mkdir(parents=True)
auditpath=O/'procurement_candidates.audit.json'
for p in list(outputs)+[auditpath]:
 if p.exists():
  q=backup/p.relative_to(R);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);assert sha(p)==sha(q)
for p,t in outputs.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8')
with (O/'procurement_candidates.csv').open() as f:readback=list(csv.DictReader(f))
assert len(readback)==81 and [r['Reference'] for r in readback]==[p.ref for p in D.PARTS]
assert sum(int(r['PurchaseQtyPerBoard']) for r in readback)==78
assert all(r['ManufacturerMPN']=='N/A' and r['PurchaseQtyPerBoard']=='0' for r in readback if r['Reference'] in {'TP2','TP3','TP4'})
after={str(p.relative_to(R)):sha(p) for p in protected};assert before==after
report=dict(status='PASS_DOCUMENT_COVERAGE_ONLY',reference_count=81,fitted_position_count=78,fab_only_position_count=3,protected_sha256_before=before,protected_sha256_after=after,protected_files_unchanged=True,physical_or_electrical_qualification_complete=False,stock_or_prices_verified=False,kicad_or_hardware_generators_invoked=False,backup_directory=str(backup.relative_to(R)),output_sha256={str(p.relative_to(R)):sha(p) for p in outputs})
auditpath.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if not k.startswith(('protected_sha','output_sha'))},indent=2))

