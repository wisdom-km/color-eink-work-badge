# P36 驱动及完整软件验证

真实最终证据：hardware/portrait/verification/visible-final。可见运行visible_final_checks.sh：驱动387例（日志386是中间轮，不能相加）+5GPIO/SPI模型；USB469接收边界/100000畸形字节/11sender例；手机协议43、服务电源模型23、DOM8；完整图像测试及PIO编译。最新RAM45932、Flash784080，最终看pio.log。ASan/UBSan启用，LSan受ptrace限制。

驱动逐字对照固定Waveshare源120061SPI字节；适配模型与故障注入不代表实体SPI/屏BUSY/RF。完整固件使用单120000B缓冲，已实现手机和USB传输；未实机。工具链来源见tools/portrait_environment。包内oracle命令：bash tools/portrait_driver/run_tests.sh third_party/waveshare-3in6e-ESP32/EPD_3in6e.cpp。
