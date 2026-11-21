# 现有软件与兼容范围

本表区分“现有软件具备该连接路径”与“Calxus 工程样机已实测”。截至 2026-11-21，已完成来源核对和 SilverLink 参考固件构建；尚无本版 PCB 的实物传输结果。下面的“待测”不是功能通过标记。

| 目标 | Calxus 档位/路径 | 现有软件 | 已查证边界 | Calxus 实测 |
|---|---|---|---|---|
| TI 2.5 mm 双线 Link 机型 | `10`，SilverLink B | TI Connect 经典版、TILP、WebTILP | 需软件支持该具体型号；USB 身份为 `0451:E001`，不是 COM | 待测 |
| TI 原生 USB 机型 | `00` Mini-B 或 `01` 原装 USB 线 | 对应 TI Connect / TI Connect CE / Nspire 软件，或支持该型号的 WebTILP | 使用计算器自己的 USB 协议和驱动 | 待测 |
| CASIO ALGEBRA FX / CFX / fx-7400G 等串口场景 | `11` + CASIO | FA-124 COM 模式及现有兼容工具 | COM1..COM9 等限制随软件；CH343 不仿真 SB-88 的 USB VID/PID | 待测 |
| CASIO fx-9860G 原生 USB 场景 | `00` 或 `01` | FA-124 USB 模式 | 厂商手册要求原生 USB，不能用通用串口代替；本版无 USB Hub | 待测 |
| HP 50g / 已核对的 HP 串口机型 | `11` + AUX 专用尾线 | 支持该机型和协议的 HP 连接软件、Kermit/串口工具 | 电平、针序、串口开启/关闭行为按机型验证 | 待测 |
| TI-Nspire 开机/运行日志 | `11` + AUX 专用尾线 | 现有串口终端 | TTL UART、常用 115200 8N1；仅日志路径，不等同文件管理 USB | 待测 |
| 通用 USB 外设 | `01` | 上行主机现有驱动和应用 | 依赖主机供电与驱动；Calxus 不新增 USB Host | 待测 |

## Windows 驱动按目标设备配置

| 设备阶段 | 典型驱动要求 | 不应混淆的用途 |
|---|---|---|
| SilverLink `0451:E001`，TI Connect | 对应 TI 原厂驱动 | 不保证该绑定可被浏览器 WebUSB 打开 |
| SilverLink `0451:E001`，WebTILP | WinUSB，浏览器授予 USB 权限 | 替换驱动后原厂软件可能无法打开同一设备 |
| TUSB3410 ROM `0451:3410` | TI Burner 的 Aploader，或开发下载工具所需驱动 | 这是烧录阶段，不是正常 SilverLink |
| CH343P UART | WCH 官方 VCP/CDC 驱动形成 COM 口 | 保持串口驱动；不为 WebTILP 把它换成 WinUSB |
| 原生 USB 计算器 | 原厂软件/该工具要求的目标设备驱动 | Calxus 的硬件数据开关没有自己的 USB 驱动 |

浏览器版通常需要支持 WebUSB 的 Chromium 系浏览器。不同浏览器/系统版本和具体计算器的支持情况由 WebTILP 当前版本决定；设备能出现在浏览器授权列表不代表该机型全部功能已通过。桌面 TILP 与 WebTILP 的 Windows 驱动要求也不能一概视为相同。

## 三处需要按用途区分

**TI 双线与 USB-UART。** TI Link 是计算器双线握手协议，由 TUSB3410 固件处理；将它接到 CH343 TX/RX 不会得到 SilverLink。使用现有软件的兼容目标是完整的 USB 协议行为，不只是设备名称。

**CASIO COM 与原生 USB。** CASIO FA-124 2.04 手册 E-19、E-38 指定部分机型使用 COM；E-3 明确限制 fx-9860G 系列的普通串口替代连接。E-4 的系统要求还明确排除 USB Hub。最终硬件采用 CH444G USB 数据切换而非 Hub；该拓扑仍需实物信号和枚举验证，不能把“没有 Hub”写成原厂认证。

**HP/Nspire UART 与文件协议。** AUX 提供串口电气通道。文件传输须由已有软件实现目标协议；Nspire 系统日志也不会自动变成 TI-Nspire USB 文件管理接口。不同计算器的专用插头、电平或电池触点不能通用短接。

来源见[技术来源索引](sources.md)。
