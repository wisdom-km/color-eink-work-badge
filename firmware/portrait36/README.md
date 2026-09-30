# P36 手机与USB六色更新固件

400×600、每像素4bit，单缓冲120000B，颜色黑0白1黄2红3蓝5绿6；不兼容H2屏。完整用户流程见docs/portrait/START_HERE.md。

长按UPDATE(GPIO1)约2秒启动限时本地SoftAP；屏上给临时SSID/密码/32hex连接码，手动输入，没有配对QR。页面处理图片、六色量化、CRC和≤4096B分块；全部API临时token校验，最多1客户端10分钟，不使用用户既有WiFi凭据。上传合法完整后独立SHOW，成功后30秒状态窗口再关AP。USB同一会话锁，send_frame.py先校验再SHOW。

单缓冲无旧RAM回滚、无Flash/NVS图片持久化，重启EMPTY；无效包不刷新屏但可覆盖RAM。配对页会覆盖先前画面。手机真实浏览器/WiFi/堆峰值未实测；DOM8场景是模拟。

GPIO：电源2 LOW开；SCK6、MOSI7、CS10、DC20、RST21、BUSY3 LOW忙；UPDATE1 RTC唤醒；VBUS ADC4；电池ADC0；BOOT9仅维护。SPI mode0 MSB-first1MHz。所有返回硬断屏电源，控制线LOW，BUSY INPUT无上拉；04/12/02操作要求有界LOW→HIGH。无SPI物理ACK，超时边界待实屏温区验证。

60秒无USB/AP/上传且UPDATE释放后深睡；短按UPDATE唤醒USB，插USB本身不保证唤醒。电源阈值电池估算≥3.6V或VBUS ADC≥1000mV，真实ADC/峰值需校准。初次仅受控台架测试。

仓库根source tools/portrait_environment/env.sh，然后pio run -d firmware/portrait36。完整host套件bash tools/portrait_driver/visible_final_checks.sh。最新编译RAM45932B、Flash784080B；最终以pio.log为准。测试为host/adapter模型、真实编译，不代表硬件成功。本源码包不附固件镜像；样帧.bin绝不是烧录文件。厂商序列与许可见THIRD_PARTY_NOTICES.md。
