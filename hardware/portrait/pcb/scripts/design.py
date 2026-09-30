"""P36 electrical candidate, derived from primary source reference circuitry.
H2 is imported read-only; this module never regenerates or modifies H2.
Root hardware/pcb/scripts/design.py PORTRAIT owns mechanical dimensions.
Not a production release; see docs/portrait and the verification directory.
"""
import importlib.util, sys, copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('h2_design',ROOT/'hardware/pcb/scripts/design.py')
H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)
Part=H.Part;R=H.R;C=H.C
KICAD_SYM=str(Path(__file__).resolve().parents[1]/'lib/pinned-symbols');KICAD_FP=str(Path(__file__).resolve().parents[1]/'lib/pinned-footprints')
PROJECT_FP='lib';ESPRESSIF_SYM='lib/Espressif.kicad_sym'
BOARD_W=58.0;BOARD_H=92.64;BOARD_THICKNESS=.8;BOARD_CORNER_R=2
PANEL_H=86.6;PANEL_T=.78
BATTERY_POCKET=(4,5,30,51)
ESP_ANT_KEEPOUT=(32.4,0,56.6,15.5)
FPC_SLOT=(13,88,41.2,89.4)
SILK_BACK=[('P36 E6 PROTOTYPE',29,52,1.0,.15),('NOT PRODUCTION',29,54,0.8,.12)]
SILK_REF_XY={};SILK_REF_OFFSET={}
PARTS=[copy.deepcopy(p) for p in H.PARTS if p.section in ('USB','POWER','MCU')]
P={p.ref:p for p in PARTS}
positions={
'J3':(50,89.94,0),'R1':(44,84,90),'R2':(55.5,84,90),'C1':(53,78,90),
'U3':(47,66,0),'R3':(43.5,66,0),'R4':(53,83,90),'D4':(55.5,81,0),'C2':(43,70,0),
'J2':(9,54,0),'U4':(45,58,0),'C3':(41,58,90),'C4':(49,58,90),
'R5':(34,46,0),'R6':(38,46,0),'C5':(42,46,0),'TP4':(5,59,0),'TP2':(5,62,0),'TP3':(3,47,0),
'U1':(45,18,0),'C6':(35.8,22,90),'C7':(35.8,24.5,90),'R7':(35.8,27,90),
'C8':(35.8,29.5,90),'R8':(54.5,27,90),'R10':(54.5,30,90),'R9':(53,39,90),
'D5':(53,42,0),'SW1':(6,88,0),'SW2':(7.5,83.5,0)}
for ref,at in positions.items():P[ref].at=at
# Proper named charger, conservative 100mA target; matched cell still a purchasing gate.
P['U3'].value='MCP73831T-2ACI/OT';P['U3'].desc='Microchip MCP73831 4.2V charger; 10k PROG nominal100mA; protected single-cell LiPo only';P['U3'].lcsc=''
P['R3'].value='10k';P['R3'].desc='MCP73831 RPROG10k -> nominal100mA, verify actual cell rating'
P['U1'].value='ESP32-C3-MINI-1-N4X';P['U1'].desc='Espressif current C3 MINI1 N4X; module antenna clearance and RF on-body test required';P['U1'].lcsc=''
# Door access uses physically independent authorised card, not ST25 Type5 emulation.
for pin in ('13','18','19'):
    del P['U1'].pins[pin];P['U1'].nc.append(pin)
# AN1149-style load sharing isolates cell charger from system current.
P['U4'].pins['1']='VSYS';P['U4'].pins['3']='VSYS';P['C3'].pins['1']='VSYS'
PARTS += [
 Part('Q10','Transistor_FET','AO3401A','Package_TO_SOT_SMD:SOT-23','AO3401A',{'1':'VBUS','2':'VSYS','3':'VBAT'},section='POWER',at=(39,64,0),desc='P-MOS battery load-share, sourceVSYS/drainVBAT; body diode VBAT->VSYS; AN1149 topology'),
 R('R20','100k','VBUS','GND',at=(36,64,90),section='POWER'),
 Part('D10','Diode','SS14','Diode_SMD:D_SMA','SS14',{'1':'VSYS','2':'VBUS'},section='POWER',at=(47,73,0),desc='USB to VSYS Schottky40V1A; evaluate thermal and droop'),
 C('C30','22u','VSYS','GND',at=(38,58,90),fp='Capacitor_SMD:C_0805_2012Metric',section='POWER',desc='22uF10V X5R0805'),
]
# 50pin panel pin map from Waveshare3.6E6 reference J1, page1; NC kept explicit.
pinmap={2:'TFT_VCOM',3:'FPL_VCOM',5:'GDRH',6:'RESEH',8:'GND',9:'GDRC',10:'RESEC',11:'VPC',12:'GND',13:'VGL',14:'VPH',15:'VSH',16:'VSH_LV',17:'VSH_LV2',18:'VSL',19:'VSL_LV',20:'VSL_LV2',21:'GND',22:'REFN',23:'REFP',26:'GND',27:'GND',28:'EPD_RST',29:'EPD_BUSY',30:'EPD_DC',31:'EPD_CS',32:'EPD_SCK',33:'EPD_MOSI',37:'VDDDO',38:'EPD_3V3',39:'GND',40:'EPD_3V3',41:'VCP2',42:'CP2N',43:'CP2P',44:'VCP1',45:'CP1N',46:'CP1P',49:'VGH',50:'VCOMBD'}
PARTS.append(Part('J1','Connector_Generic','Conn_01x50','badge:FH34SRJ-50S-0.5SH','EPD50 FH34SRJ', {str(k):v for k,v in pinmap.items()},nc=[str(i) for i in range(1,51) if i not in pinmap],section='EPD',at=(27.09,83,0),desc='Hirose FH34SRJ-50S-0.5SH(50); .5pitch50P dualcontact .3FPC; pending footprint drawing verification'))
PARTS += [Part('Q20','Transistor_FET','AO3401A','Package_TO_SOT_SMD:SOT-23','AO3401A',{'1':'EPD_PWR_EN','2':'+3V3','3':'EPD_SUPPLY'},section='EPD',at=(50,48,0),desc='3V3 panel hard powergate; default10k gatepullup OFF; SPI pins hi-Z before poweroff'),
 C('C100','100u/6.3V','V_B','GND',at=(20,57.5,0),fp='Capacitor_SMD:C_1210_3225Metric',section='EPD',desc='100uF6.3V X5R1210; effectivecap/inrush verify'),
 C('C101','100n','EPD_3V3','GND',at=(50,44,90),section='EPD'),
 Part('FB1','Device','FerriteBead','Inductor_SMD:L_0603_1608Metric','BLM18PG121SN1D',{'1':'EPD_SUPPLY','2':'V_B'},section='EPD',at=(46,41,0),desc='Murata BLM18PG121SN1D from vendorboost reference'),
]
# High-voltage reference analog stage. Capacitor ref map retained in SOURCE_REFERENCE.
for ref,n1,n2,at in [('L1','V_B','SW_H',(9,69,0)),('L2','SW_C','RESEC',(33,70,0))]:
 PARTS.append(Part(ref,'Device','L','Inductor_SMD:L_Changjiang_FNR4018S','10uH',{'1':n1,'2':n2},section='EPD',at=at,desc='10uH shielded4x4x1.8; Isat>=1A target pending vendor peak-current test; no47uH substitute'))
PARTS += [Part('Q1','Transistor_FET','AO3400A','Package_TO_SOT_SMD:SOT-23','AO3400A',{'1':'GDRH','2':'RESEH','3':'SW_H'},section='EPD',at=(14,68,0),desc='N-MOS as vendorAO3400 stage'),Part('Q2','Transistor_FET','AO3401A','Package_TO_SOT_SMD:SOT-23','SI2301CDS-T1-E3',{'1':'GDRC','2':'V_B','3':'SW_C'},section='EPD',at=(29,65,0),desc='Vishay P-MOS exactly vendor negative-boost stage')]
for ref,val,n1,n2,at,fp in [('R100','1M','GDRH','GND',(14,64,0),'Resistor_SMD:R_0603_1608Metric'),('R101','0.2R','RESEH','GND',(14,71,0),'Resistor_SMD:R_0805_2012Metric'),('R102','1M','GDRC','V_B',(29,61.5,0),'Resistor_SMD:R_0603_1608Metric'),('R103','0.2R','RESEC','GND',(33,74,0),'Resistor_SMD:R_0805_2012Metric'),('R104','0R','VPH','VGH',(23,72,0),'Resistor_SMD:R_0603_1608Metric')]:
 PARTS.append(R(ref,val,n1,n2,at=at,fp=fp,section='EPD',desc=f'{val}; vendorstage; sense resistors0.2ohm>=0.25W'))
for ref,k,a,at in [('D1','VPH','SW_H',(19,68,90)),('D2','PUMP_H','VGL',(19,73,90)),('D3','GND','PUMP_H',(24,68,90)),('D6','SW_C','VPC',(29,73,90))]:
 PARTS.append(Part(ref,'Diode','MBR0530','Diode_SMD:D_SOD-123','MBR0530',{'1':k,'2':a},section='EPD',at=at,desc='30V0.5A Schottky as vendor reference; pin1K pin2A'))
capdefs=[
('C110','4.7u/25V','TFT_VCOM','GND',(5,75,90)),('C111','470n/25V','FPL_VCOM','GND',(8,75,90)),
('C112','10u/25V','SW_H','PUMP_H',(18,63,0)),('C113','10u/25V','VPH','GND',(23,63,0)),
('C114','4.7u/25V','V_B','GND',(9,63,0)),('C115','10u/25V','VGL','GND',(23,77,0)),
('C116','10u/25V','VSH','GND',(5,79,90)),('C117','10u/25V','VSH_LV','GND',(9,79,90)),('C118','10u/25V','VSH_LV2','GND',(13,79,90)),
('C119','10u/25V','VSL','GND',(17,79,90)),('C120','10u/25V','VSL_LV','GND',(37,79,90)),('C121','10u/25V','VSL_LV2','GND',(41,79,90)),
('C122','4.7u/25V','V_B','GND',(33,62,90)),('C123','2.2u/6.3V','VDDDO','GND',(45,79,90)),
('C124','1u/50V','VCP2','GND',(36,38,90)),('C125','10u/25V','VPC','GND',(37,74,90)),
('C126','1u/50V','CP2P','CP2N',(36,33,90)),('C127','1u/50V','VCP1','GND',(40,33,90)),
('C128','1u/50V','CP1P','CP1N',(44,33,90)),('C129','470n/25V','VCOMBD','GND',(48,33,90)),
('C130','1u/50V','REFN','GND',(5,71,90)),('C131','1u/50V','REFP','GND',(5,67.5,90))]
for ref,val,n1,n2,at in capdefs:
 fp='Capacitor_SMD:C_0805_2012Metric'
 PARTS.append(C(ref,val,n1,n2,at=at,fp=fp,section='EPD',desc=val+' X7R/X5R0805; voltage-rated; DC-bias capacitance vendor verification required'))
PWR_FLAG_NETS=['GND','VBUS','VSYS','EPD_3V3']
NET_CLASSES={'Default':{'clearance':.15,'track':.2,'via':.6,'via_drill':.3,'nets':[]},'Power':{'clearance':.2,'track':.4,'via':.6,'via_drill':.3,'nets':['VBUS','VBAT','VSYS','+3V3','EPD_3V3','V_B','SW_H','RESEH','SW_C','RESEC']}}
SECTION_NOTES={'USB':'USB-C native programming;5.1kCC; powerbudget must be measured','POWER':'MCP73831 nominal100mA+AN1149 loadshare; battery protection external','MCU':'ESP32-C3-N4X; boundedrefresh firmware; independent door card','EPD':'Waveshare3.6E6/50pin reference; six-color; no legacy24pin compatibility','NFC':'No NFC tag active electronics; authorised detachable access card'}
all_nets=lambda:sorted({n for p in PARTS for n in p.pins.values()})
exclude_from_bom=H.exclude_from_bom;board_footprint_id=H.board_footprint_id;nc_unconnected_net=H.nc_unconnected_net
# Pinned KiCad9 USB symbol shell is S1 (KiCad10 renamed it SH); matching physical pad naming.
P['J3'].pins['S1']=P['J3'].pins.pop('SH')
def nc_unconnected_net(ref,pad_number):
 if ref=='U1' and pad_number in ('13','18','19'):
  name={'13':'GPIO1{slash}ADC1_CH1{slash}XTAL_32K_N','18':'GPIO4{slash}ADC1_CH4','19':'GPIO5{slash}ADC2_CH0'}[pad_number]
  return f'unconnected-({ref}-{name}-Pad{pad_number})'
 return H.nc_unconnected_net(ref,pad_number)
# USB ESD reference device; device rating does not certify the entire badge.
PARTS.append(Part('U5','Power_Protection','USBLC6-2SC6','Package_TO_SOT_SMD:SOT-23-6','USBLC6-2SC6',{'1':'USB_DP','2':'GND','3':'USB_DN','4':'USB_DN','5':'VBUS','6':'USB_DP'},section='USB',at=(49,80,0),desc='ST USBLC6-2SC6; DS4260pinmap; short GNDreturn; systemESDtest pending'))

# Separate logic/boost ferrite branches match the vendor reference; C100 reservoir is AFTER boost ferrite.
PARTS.append(Part('FB2','Device','FerriteBead','Inductor_SMD:L_0603_1608Metric','BLM18PG121SN1D',{'1':'EPD_SUPPLY','2':'EPD_3V3'},section='EPD',at=(41,41,0),desc='Separate logic ferrite branch as vendor reference; EPD_SUPPLY is gated3V3'))
NET_CLASSES['Power']['nets'].append('EPD_SUPPLY')
# Achievable protected prototype pack: Adafruit1578 (vendor500mAh pack; incoming lot inspection required).
# 31x38x5.6mm is conservative engineering envelope, NOT vendor guaranteed max/aged swelling guarantee.
BATTERY_POCKET=(0.8,4.0,32.2,43.0)
WIRE_POCKET=(14.0,44.0,31.0,50.5) # reserved area for full original100-102mm insulated lead loop; trialfit required
P['J2'].footprint='Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal'
P['J2'].value='JST PH2.0 battery'
P['J2'].desc='JST S2B-PH-SM4-TB; mateAdafruit1578 originalPHR2plug; polarity MUST match supplier keyedface and prepower measurement; no genericreverselead'
P['J2'].lcsc=''
P['TP4'].at=(3,59,0)
# Mate the PH plug from the empty lead bay ABOVE J2, away from the boost components.
P['J2'].at=(9,54,180)
# Adafruit JSTPH convention: physical contact1 GND, contact2 positive (not H2SHL convention).
P['J2'].pins={'1':'GND','2':'VBAT'}
P['J2'].desc='JST S2B-PH-SM4-TB; Adafruit1578 keyedPHR2 mate: contact1GND/contact2VBAT; verify incoming lot keyedface+voltage beforepower; retain original lead'
# Dedicated RTC update/wake key; GPIO9 remains BOOT/ROM service only.
P['U1'].pins['13']='WAKE_n'; P['U1'].nc.remove('13')
PARTS.append(Part('SW3','Switch','SW_Push','Button_Switch_SMD:SW_SPST_PTS810','UPDATE',{'1':'WAKE_n','2':'GND'},section='MCU',at=(6,46,0),desc='RTC GPIO1 active-low wake/update; longpress for limited-time phone AP'))
PARTS.append(R('R21','100k','+3V3','WAKE_n',at=(10,46,90),section='MCU',desc='External100kRTCwakepullup; sleep only afterrelease'))
P['TP3'].at=(3,64,0)
# ADC1 VBUS detection: avoid treating Serial/DTR or an idle cable as actual power evidence.
P['U1'].pins['18']='VBUS_SENSE'; P['U1'].nc.remove('18')
PARTS += [R('R22','1M','VBUS','VBUS_SENSE',at=(54,50,90),section='POWER'),R('R23','330k','VBUS_SENSE','GND',at=(54,53,90),section='POWER'),C('C32','100n','VBUS_SENSE','GND',at=(50,53,0),section='POWER')]

SECTION_NOTES['NFC']='Internal authorized access credential unresolved; no external card sleeve; no universal access compatibility claim'
SECTION_NOTES['MCU']='ESP32-C3-N4X; RTCGPIO1 UPDATE; bounded display; GPIO4 VBUS ADC; internal credential reserved'
# PH plug envelope requires UPDATE to the left of the plug; normal finger button is a case flexure.
next(p for p in PARTS if p.ref=='SW3').at=(3,46,0)
next(p for p in PARTS if p.ref=='R21').at=(10,60,90)
for _ref in ('SW1','SW2','SW3'):
 _p=next(p for p in PARTS if p.ref==_ref)
 _p.desc='C&K PTS810; nominalheight2.5mm(+.2/-.1); travel.15+/-.1mm; actuator/flexure must be tested'



# BEGIN VISIBLE_FINAL_SOURCE_SYNC
for _ref, _at in {
    'R1': (44.2, 83.85, 90),
    'R2': (55.5, 83.85, 90),
    'R21': (14.5, 60.1, 90),
    'SW3': (3, 46, 0),
}.items():
    next(p for p in PARTS if p.ref == _ref).at = _at
assert NET_CLASSES['Power']['track'] == 0.4
NET_CLASSES['Power']['nets'] = [n for n in NET_CLASSES['Power']['nets'] if n != 'RESEC']
NET_CLASSES['Sense'] = {'clearance': 0.2, 'track': 0.2, 'via': 0.6, 'via_drill': 0.3, 'nets': ['RESEC']}
# END VISIBLE_FINAL_SOURCE_SYNC
