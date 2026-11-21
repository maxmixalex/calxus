# 技术来源索引

核对日期：2026-11-21。链接用于追溯器件事实、原有协议实现和软件行为。它们不表示来源作者已测试或认可本版 Calxus。

| 来源 | 具体位置 / 版本 | 用于本工程 |
|---|---|---|
| [queueRAM/ti_graph_link 固定提交](https://github.com/queueRAM/ti_graph_link/tree/f0db48b761ca64f77ad3d27dd3d0a98930638d04) | README、Makefile、`ti_graph_link_silver.asm`、`.sha1`、`tools/generate_eeprom.py` | SilverLink B 的硬件、GPIO、反汇编程序与可复现构建 |
| [TUSB3410 数据手册](https://www.ti.com/lit/ds/symlink/tusb3410.pdf) | SLLS519J；§5.5.2、§5.6.2、§5.6.3、§5.6.6、§5.6.7 | 8052、RAM/ROM、EEPROM 与 USB 启动、头格式、下载端点和引导 ID |
| [TUSB3x10 EEPROM Burner](https://www.ti.com/lit/ug/sllu205/sllu205.pdf) | SLLU205；§2、§3.2、§3.6、§3.9、§4.2 | Aploader、完整二进制写入、容量设置与 EEPROM 读回 |
| [Using the TUSBxxxx EEPROM Programmer](https://www.ti.com/lit/an/slla179b/slla179b.pdf) | SLLA179B；§2、§5.1、§5.2 | SCL 隔离、枚举后恢复 EEPROM、WP 低使能写入；旧工具不能代替读回校验 |
| [TUSB3410 GPIO EVM](https://www.ti.com/lit/ug/sllu041/sllu041.pdf) | SLLU041；§2.6、§2.7 | 可拆 SCL 跳帽绕过 EEPROM 的硬件方法 |
| [24LC64 数据手册](https://ww1.microchip.com/downloads/en/DeviceDoc/21189T.pdf) | Microchip 24AA64/24LC64，器件容量、页写与 WP | 64 kbit 容量、32 字节页写、3.3 V EEPROM 编程 |
| [WCH CH440/442/444 产品页](https://www.wch.cn/products/CH440.html) | CH444G 双通道四选一模拟开关 | 四档原生 USB 数据路径，不枚举为 USB Hub |
| [WCH CH440 系列数据手册入口](https://www.wch.cn/downloads/CH440DS1_PDF.html) | CH440 系列手册，本次实际审阅版本 3E | CH444G 控制选择与 USB 信号能力 |
| [Alps SSSS224100](https://tech.alpsalpine.com/e/products/detail/SSSS224100/) | 官方尺寸图与电路图，双刀四档 nonshorting | SW1 公共脚 3/8、每档触点及机械尺寸 |
| [TPS2552 数据手册](https://www.ti.com/lit/ds/symlink/tps2552.pdf) | SLVS841G；DBV 引脚、反压保护、限流表 | 三分支低有效供电开关，限流与反灌响应边界 |
| [SN74LVC1G07](https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf) / [SN74LVC1G17](https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf) | TI 官方手册，DBV 引脚及 Ioff | UART 非反相开漏发送、耐受输入与掉电行为 |
| [WCH CH343 产品页](https://www.wch.cn/products/CH343.html) | CH343P；官方数据手册与驱动入口 | USB-UART 和配置用途 |
| [WCH CH343SER](https://www.wch.cn/downloads/CH343SER_EXE.html) | 官方 Windows 驱动入口 | COM 端口驱动来源；实际系统版本另记录 |
| [CASIO FA-124 2.04 用户手册](https://edu.casio.com/education/support_software/dl/PC_links/FA-124_E.pdf) | E-3 / E-4 / E-19 / E-38 / E-50 | 原生 USB 与 COM 场景区分、COM1..9、厂商连接条件 |
| [piotrva/casio-link](https://github.com/piotrva/casio-link) | 作者对 fx-7400G PLUS 的实测连接表 | 直插公头 Tip=计算器TX、Ring=计算器RX；9600 8N2 为该机型场景 |
| [Arduino-Casio-Serial-library](https://github.com/nsg21/Arduino-Casio-Serial-library) | 原作者 README 的 Physical connection | 自制直插公头与使用 SB-62 交叉线的母座接法区别 |
| [Michael Fenton CASIO 接口实测](https://mikefentonnz.github.io/projects/casio-calculator-esp8266.html) | FX-9750G Plus / FX-9750GIII 电气与数据记录 | Tip/Ring 方向、不同代际电平和开漏发送依据；不代替 Calxus 实测 |
| [CASIO FA-124 系统支持页](https://support.casio.com/en/support/osdevicePage.php?cid=004002017) | FA-124 Ver.2.04 | SB-88 / SB-88(A) 在所列系统中的限制，不能推成 CH343 仿真 |
| [WebTILP 项目页](https://tiplanet.org/scripts/webtilibs/) | 现有 WebUSB / SilverLink 路径 | 无需新增日常上位机的浏览器方案 |
| [WebTILP 作者说明](https://www.cemetech.net/forum/viewtopic.php?p=315447) | Adriweb，2026-05-20 的 Windows 说明 | 对目标 TI 设备使用 WinUSB，避免替换其他 USB 设备驱动 |
| [WebTILP 发布说明](https://tiplanet.org/forum/viewtopic.php?p=280020) | 项目维护者的支持范围与限制 | USB 型线缆、浏览器限制及 Windows 驱动切换 |
| [HP 50g 串口线原设计者说明](https://commerce.hpcalc.org/serialcable.php) | Eric Rechlin / HPCalc | 专用电平、RX 在关闭时可能被驱动、不能加超过 3.3 V |
| [HP 50g 串口线设计记录](https://www.allenwan.com/hpcalcserialcable/) | Allen Wan | 计算器侧 TTL/CMOS 与外部 RS-232 转换的区别 |
| [HP 39gs 原厂使用指南](https://h10032.www1.hp.com/ctg/Manual/c00751802.pdf) | HP，F2223AA-90001，第 19-4 至 19-6 页（PDF 第 270–272 页） | 五针 Mini-USB 原生 USB 与 PC Connectivity Kit；与四针串口区分，未给出可直接采信的 AUX 电气针序 |
| [Hackspire Hardware / UART](https://www.hackspire.org/Hardware/#uart) | UART 与 dock 研究记录 | Nspire TTL 日志串口、115200 8N1；具体硬件版本须再核对 |

## 来源与交付边界

SilverLink 参考程序被上游标记为从 EEPROM 提取的反汇编。固定提交中没有 LICENSE/COPYING 文件。本项目只在自有文档中说明其来源及实际构建结果，发布获取与构建脚本，不把该上游程序改标为 Calxus 自有许可。TI、CASIO、HP、WCH 的手册和工具使用各自原始来源。

构建脚本对上游源文件和产物均作内容校验。网页中的兼容描述仅作为测试依据；本版样机的合格结果以实际记录为准。
