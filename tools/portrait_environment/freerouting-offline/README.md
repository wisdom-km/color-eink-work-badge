# Freerouting 2.4.1 网络行为审计与本地候选

日期：2026-09-30。审计固定官方 commit `ae3d377740b6ffa744bed1bab26625fe0278fa90`。这是软件源代码与编译产物审计，不是一次用户PCB路由。

## 原版结论

1. CLI 的布线计算在本地进程完成，并非把原始 DSN 提交云端路由。
2. **默认遥测启用**，会向 `https://api.freerouting.app/v1/analytics/identify` 与 `/track` 发 POST。原 CLI 并不等于零外联。
3. `-da` 或 `--usage_and_diagnostic_data.disable_analytics=true` 可关闭遥测；`--profile.allow_telemetry=false` 也会关闭同一发送开关。
4. **找不到关闭版本检查的官方设置**。版本检查无条件查询 GitHub releases/latest，甚至 `-help` 也先启动该线程。因此不能把这些参数称为“严格离线模式”。
5. 本次源码审计没有运行原版或新候选JAR，没有执行任何用户DSN，也没有复试原被拒绝的命令。

### 原版调用路径与精确行号

所有行号对应上面的未修改官方 commit，基址：
https://github.com/freerouting/freerouting/blob/ae3d377740b6ffa744bed1bab26625fe0278fa90/

- `src/main/java/app/freerouting/Freerouting.java:80–163`：创建本地 Session/Job，读取文件，等待本地 scheduler
- `src/main/java/app/freerouting/core/RoutingJob.java:446–453`：FileInputStream/readAllBytes
- `src/main/java/app/freerouting/management/jobs/RoutingJobScheduler.java:90–96,236–241`：加载本地 DSN 对象、创建/启动线程
- `src/main/java/app/freerouting/management/jobs/RoutingJobSchedulerActionThread.java:99–167`：RoutingPipeline.createForHeadless(job)，pipeline.run()
- `src/main/java/app/freerouting/Freerouting.java:197–224`：Files.write 保存输出
- `src/main/java/app/freerouting/settings/UsageAndDiagnosticDataSettings.java:10–12`：disableAnalytics 默认 false
- `src/main/java/app/freerouting/settings/UserProfileSettings.java:17–19`：allow_telemetry 默认 true
- `src/main/java/app/freerouting/Freerouting.java:1269–1270,1318–1319,1360–1386`：先读取env/CLI，再设置遥测enabled；关闭参数在首次identify之前生效
- `src/main/java/app/freerouting/settings/GlobalSettings.java:516–555,814–817`：通用 `--key=value` 与 `-da` 解析
- `src/main/java/app/freerouting/analytics/FreeroutingAnalyticsClient.java:24,75–115,158–190`：HTTP发送端点、enabled guard、POST JSON、identify/track
- `src/main/java/app/freerouting/Freerouting.java:1416–1426`：无条件版本线程早于帮助退出
- `src/main/java/app/freerouting/util/VersionChecker.java:18–19,69–89`：固定GitHub URL、User-Agent=Freerouting-Version-Checker、无body的GET请求；没有设置开关

### 默认可能传送的内容

- identify：配置生成的profile ID、email（如有）、OS/版本/语言、同意设置。`FRAnalytics.java:274–293`
- appStarted：原始命令行字符串（可含输入/输出文件名）、软件/Java/OS、CPU/RAM/语言等。`FRAnalytics.java:388–428`；调用处 `Freerouting.java:1397–1414` 传的是 `String.join(" ",args)`
- fileLoaded：board statistics JSON，含尺寸/bounding box、元件/层/网/走线等统计；不等同于完整DSN。`HeadlessBoardManager.java:759–779`、`FRAnalytics.java:549–575`、`core/scoring/BoardStatistics.java:35–78`
- routing/optimizer：全局settings JSON、运行时间、最终board hash/未连网/间距统计等。`FRAnalytics.java:466–540`
- 异常：异常消息、异常文字、stacktrace。`FRAnalytics.java:592–610`

源码可以证明“有尝试发送的路径”，**不能证明先前某次请求实际已被远端接收**。先前只带 `-help` 的安装烟雾测试没有输入PCB文件，但原版仍可能尝试发应用元数据遥测及版本GET；不能回溯声称那次严格零外联。

### 原版降低风险参数，不是完整离线保证

`-da --profile.allow_telemetry=false --gui.enabled=false --api_server.enabled=false --mcp_server.enabled=false --mcp_server.stdio=false`

它们可关闭遥测与服务器/GUI；仍无法禁用上述GitHub版本请求。没有使用假代理、放宽TLS或规避既有安全限制来掩盖这个缺口。

## 独立本地候选修改

工作副本：`/workspace/scratch/200245c5fbc3/toolchain/freerouting-offline-source`

`local-only.patch` 是针对官方固定commit的补丁；未修改原始clone或原始官方JAR。仅6个Java文件改变：

- `FRAnalytics.setAccessKey` 不构造backend，analytics保持null
- FreeroutingAnalyticsClient、SegmentClient、BigQueryClient 的发送方法为no-op
- BigQuery service创建返回null，不解析凭据、刷新token或连接Google
- VersionChecker不构建HTTP client，run()为no-op；main不再启动版本线程
- main在解析CLI/env后强制禁用GUI/API/MCP/telemetry，参数不能重新开启
- REST/MCP工厂均直接返回null，防止监听器/代理分支意外开启
- 启动文字明确包含 LOCAL-ONLY PATCHED BUILD

`verify_offline_source.py` 验证上述静态条件，并确认277个routing/board/geometry/core/rules/io/drc/management文件与官方逐字相同。结果在 `static-verification.json`。注意：归档仍含不可达的服务器/GUI与第三方依赖类，不能用字符串搜索“仍有https”判断是否调用；也不能把源码证明替代为运行时网络隔离证明。

GPL-3.0保留，见 `FREEROUTING-GPL-LICENSE.txt` 与原始source `LICENSE`。这不是badge项目的MIT脚本代码重新许可。保留官方源commit、完整本地副本、patch、编译与封装脚本，不伪称官方发布版本。

## 构建状态与替代路径

- Temurin JDK25.0.4.1+1 官方包校验成功
- 官方 Gradle9.7.1 distribution与原wrapper内SHA256匹配
- 官方 executableJar构建尝试失败：当前Java/Gradle对foojay插件解析失败，未进入编译；见gradle日志。未禁用TLS校验或添加信任证书
- 经任务负责人确认，改用JDK25 javac对6个修改类编译，以哈希固定的官方v2.4.1 fat JAR作classpath，退出0
- `package_overlay.py` 验证官方JAR SHA，替换6个类及其旧inner classes，保留其他归档项逐字一致；写新版本标记/patch hash
- 明确这是**javac overlay候选，不是通过官方Gradle的完整源码构建**

最终候选、SHA、所有替换类和原封装对照数量见 `artifact-manifest.json`。反编译证据在 `candidate-bytecode.txt`。没有运行候选。

## 下一步仅限审查后的无用户数据烟雾测试

1. 先审核patch、源码静态结果、javap no-op方法与候选SHA
2. 若获准执行新候选，使用本目录单独生成的 `synthetic.dsn`，新空配置目录、相对SES输出、交互shell、日志重定向；不传用户板
3. 先-help再synthetic一轮，观察网络系统调用；期望没有外部HTTP/DNS/connect，生成非空synthetic.ses
4. 核实输出可解析、程序正常退出，检查日志明确LOCAL-ONLY；仍不能以exit0替代DRC或路由完成指标
5. 任何外部网络尝试、未知开关、artifact hash不一致或审查拒绝即停止，不试原始遥测命令
6. 用户板的后续执行由负责人在审查证据后单独决定，本次没有授权运行它

这份文档不批准原来被拒绝的上传路径，也不批准改变系统网络/安全设置。
