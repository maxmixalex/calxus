# Calxus 转换器固件与恢复

本目录处理 **Calxus 自身的 TUSB3410 转换固件**。计算器的系统和程序传输仍由 TI Connect、WebTILP、FA-124 或对应 HP 软件执行。日常使用不需要运行这里的构建脚本。

## 已实际完成

2026-11-21 在 Linux 容器中，用 SDCC 4.2.0 #13081 汇编了 queueRAM/ti_graph_link 固定提交 `f0db48b761ca64f77ad3d27dd3d0a98930638d04` 的 SilverLink B 程序。5120 字节程序与上游公布的 SHA-1 一致。详见 [构建记录](validation/BUILD_RECORD.json) 和 [构建日志](validation/build.log)。这证明源文件和编译产物可复现，**没有代替 Calxus PCB 上的烧录、USB 枚举和计算器实测**。

| 产物 | 大小 | 用途 |
|---|---:|---|
| `ti_graph_link_silver.bin` | 5120 字节 | 裸 8052 程序；不是完整 EEPROM 镜像 |
| `ti_graph_link_silver.hex` | 12430 字节文本 | SDCC 生成的 Intel HEX；用于检查与开发 |
| `ti_graph_link_silver.eep` | 5126 字节 | 上游脚本输出的签名、Autoexec 头及程序 |
| `calxus_silverlink_24lc64.bin` | 8192 字节 | **推荐永久烧录文件**；含结束字节，余区填 `FF` |
| `calxus_silverlink_usb_ram.bin` | 5123 字节 | ROM USB 下载协议帧；仅临时 RAM 运行 |

裸程序 SHA-1：`6255d46f667840cccdf46e94fa7a462330076a0b`。裸程序 SHA-256：`3227e2eb733c93737c05fbf556e52afab8048e9719be72286c2d50bc0539916f`。完整 24LC64 镜像 SHA-256：`a56dc1ebb386ab03d0d60da3deb4c1583530f4063fd934c7f042a9fc6ba20af5`。

本次本机交付已将五个镜像/程序文件、构建日志和构建记录保存到 `firmware/local-build/`，共七个文件；`exports/Calxus_private_firmware.zip` 保留同样目录结构作为备份，可在工程根目录解压。原生文件系统写入后已经逐字节读回并核对 SHA-256，详见[私有交付校验记录](validation/private-delivery-record.json)。这个私有压缩包及解压目录均由 Git 忽略规则排除；公开仓库通过下述构建步骤复现，不附上游程序的二进制副本。

上游汇编文件自述为原厂 EEPROM 程序的反汇编；检查该提交的完整目录未见 LICENSE/COPYING。本工程保留来源和校验记录，不把它称作自有开源固件，也不替上游重新授予许可证。公开仓库保存构建脚本与验证记录；运行脚本时从固定上游提交取得原文件并在本地生成镜像。

## 构建

需要 Python 3、SDCC（含 `sdas8051`、`sdcc`、`makebin`）。已验证 SDCC 4.2.0；上游还报告测试过 3.8.0 至 4.2.0。无需为灰色串口线安装 gputils。

在本目录运行：

```sh
python3 build_silverlink.py --output build/silverlink
python3 verify_eeprom.py build/silverlink/calxus_silverlink_24lc64.bin
```

离线或已经下载了固定提交时：

```sh
python3 build_silverlink.py --source-dir /path/to/ti_graph_link --output build/silverlink
```

脚本先校验四个上游文件的 SHA-256，再执行上游相同汇编流程，最后同时核对裸程序 SHA-1 和 SHA-256。任何不一致均返回非零退出码。源码换行也参与校验，Windows 检出时应保留 LF。`build/` 中的二进制与临时上游文件不应被误当成 Calxus 新编写的源码提交。

## TUSB3410 的启动与可重编程方式

TUSB3410 是 **8052 + 片内 ROM 引导程序 + 代码 RAM**，没有供本工程烧写的片内应用 Flash。每次上电，ROM 优先检查 I²C EEPROM；存在有效 Autoexec 镜像时将程序装入 RAM 再执行。没有有效 EEPROM 时，ROM 使用 `0451:3410` 枚举并等待 USB 下载。参考 SilverLink 固件执行后使用 `0451:E001`。两种设备 ID 对应不同阶段。

| 操作 | 修改位置 | 拔电后 |
|---|---|---|
| USB ROM 临时下载 | TUSB3410 代码 RAM | 下载内容丢失，下次重新按 EEPROM 启动 |
| TI EEPROM Burner / 外部 I²C 编程器 | 外部 24LC64 | 保留，下次启动自动装入 RAM |
| 改 CH343P 描述符 | CH343P 的配置区 | 不会改写 TUSB3410，也不会生成新的转换协议 |

TUSB3410 不使用 SWD。WCH-Link 的 MCU 调试接口不适用于它；CH343P 的 USB-UART 功能也不是 TUSB3410 的固件下载口。

### 完整 EEPROM 格式

| 地址 | 内容 |
|---|---|
| `0x0000..0x0001` | `10 34`，TUSB3410 签名 |
| `0x0002` | `07`，Autoexec |
| `0x0003..0x0004` | `00 14`，小端程序长度 `0x1400` |
| `0x0005` | `5A`，程序所有字节之和的低 8 位 |
| `0x0006..0x1405` | 5120 字节程序 |
| `0x1406` | `00`，结束标记 |
| `0x1407..0x1FFF` | `FF`，规范化填充 |

上游 `generate_eeprom.py` 只写前 5126 字节，没有写 README 所描述的结束字节。Calxus 构建脚本保留该原始 `.eep`，另生成有明确结束字节的 8192 字节镜像，避免依赖 EEPROM 原有余区内容。24LC64 是 **64 kbit = 8 KiB**，烧录软件容量应选 64 Kb，不能选 64 KB。

## 永久写入：TI 官方 EEPROM Burner

使用 TI [SLLC443 TUSB3x10 EEPROM Burner](https://www.ti.com/product/TUSB3410) 与 [SLLU205 操作手册](https://www.ti.com/lit/ug/sllu205/sllu205.pdf)。这是已有烧录工具，不是新增计算器传输软件。该工具、Aploader 驱动和当前电脑系统的适配情况需要实机确认；本次没有安装或运行 Windows 驱动。

1. 断开所有计算器、USB-A 外设和上行 USB。将主 USB 档设为 `10`，串口选择器置 OFF。
2. 取下 J9 `EEPROM_SCL` 隔离跳帽，让 TUSB3410 的 SCL 与 EEPROM 断开。不能靠 WP 写保护进入引导：WP 只禁止写入，ROM 仍能读出旧程序。
3. 安装 TI 工具所带的 Aploader 驱动，再连接上行 USB。先出现 ROM 引导设备 `0451:3410`；Aploader 将烧录专用程序下载到 RAM，随后应出现工具识别的 HID EEPROM Burner 设备。
4. **保持 USB 连接，待烧录器设备已识别后再装回 SCL 跳帽**，使烧录程序能访问 EEPROM。将 EEPROM WP 拉低。该先断 SCL、枚举后再恢复的顺序见 TI SLLA179B §5.2。
5. 在 Burner 中选正确设备及 **64 Kb**。从 Options 启用 **Program Full Binary Image**，加载 `calxus_silverlink_24lc64.bin`，按完整镜像方式编程。该镜像已经带头；不要把它交给会再次追加格式头的普通 Program 流程。
6. 使用 **Dump EEPROM Content** 读出完整 8192 字节，保存为 `readback.bin`。运行下方命令逐字节比较。仅看到 GUI 的完成提示还不够。
7. 退出工具，拔下 USB，恢复 WP 写保护与 SCL 正常连接。重新上电后检查 SilverLink `0451:E001`。完成目录读取和小文件双向传输后再接回外壳。

```sh
python3 verify_eeprom.py build/silverlink/calxus_silverlink_24lc64.bin --readback readback.bin
```

引导阶段的 `0451:3410` 如绑定了通用 VCP、WinUSB 或其他驱动，TI Aploader 可能无法接管；只修正这个目标设备实例的驱动。日常 SilverLink `0451:E001` 的 TI Connect / WinUSB 选择见[软件兼容性](../docs/software-compatibility.zh-CN.md)。不要对电脑 USB 控制器或 CH343 串口替换驱动。

## 永久写入：外部 3.3 V I²C 编程器

适用于首板、恢复失败或不方便安装旧版 Windows 烧录器。使用支持 **24LC64、16 位字节地址、3.3 V** 的既有编程器与其软件。

1. 断开上行 USB、所有计算器和外设。在断电状态拆开 R23（SDA）和 R25（EEPROM 电源）隔离连接，并取下 J9 SCL 跳帽，使 EEPROM 的电源和总线均与主板隔离。只断开 SCL 用于强制 ROM 引导，不等同于完成外部编程所需的隔离。
2. 通过 J8 的 1/2/3/4 脚分别接编程器的 3.3 V、GND、SCL、SDA；J10 短接使 WP 拉低。此流程仅由编程器给隔离后的 EEPROM 供电，保持全部 USB 和计算器断开。
3. 选择 24LC64，先读原镜像备份。写入 8192 字节完整镜像，再全片读回并执行上述校验命令。24LC64 的 32 字节页写边界、ACK 轮询和写周期由编程器处理。
4. 先断开编程器电源和信号线，再恢复 R23、R25、J9，取下 J10 以恢复写保护，最后由上行 USB 供电验证。R23/R25 的拆装始终在断电时进行；不得将 5 V 编程器信号直接接到这组 3.3 V 网络。

具体接口编号和针脚以本版[装配与首板调试记录](../docs/assembly-and-bringup.zh-CN.md)和随附原理图为准。若所用编程器不能保证在板写入时的电源和总线隔离，先拆下 EEPROM 在插座中完成读、写、核对后再装回。

## 临时 USB RAM 下载与恢复边界

ROM 下载通道为配置 1、接口 0、Bulk OUT 端点 `0x01`，最大包 64 字节。下载数据由程序长度低字节、高字节、8 位加和校验和程序构成。本参考程序的前三字节是 `00 14 5A`。`calxus_silverlink_usb_ram.bin` 已按该格式生成；向自动加下载头的 TI loader 应提供裸 `.bin`，向原始 bulk 传输接口才提供带三字节头的 RAM 文件。它与 EEPROM 的六字节头不是同一种格式。

RAM 下载成功不能证明 EEPROM 已烧录；拔电后恢复原 EEPROM 行为是预期现象。发生自定义固件死循环、USB 描述符错误或 EEPROM 内容损坏时，拔电、断开 SCL、重新上电即可绕过 EEPROM 进入 ROM，再按永久烧录流程修复。若没有 ROM 枚举，先查电源、12 MHz 时钟、复位、USB 连线和驱动，而非反复写 EEPROM。

本次只完成 RAM 下载帧的格式生成，没有对 USB 硬件执行下载。本工程不宣称存在已经验证的跨系统“一键刷写”程序。

## 开发新的转换固件

可以针对 TUSB3410 的 8052 内核编写自己的固件并存入外部 EEPROM。若要继续直接使用现有 SilverLink 软件，需保留相应 USB 端点、命令语义、时序和 TI 双线开漏电气行为；只改 USB 名称并不获得协议兼容。新的代码需另行设置长度、校验和与镜像记录，`verify_eeprom.py --allow-custom` 仅放宽已知程序哈希检查，仍检查容量、头、校验及结束标记。

CH444G 和 CH343P 在本工程中分别承担 USB 数据切换和 USB-UART 功能，不是新增通用应用 MCU。现版可重编程应用处理器是 TUSB3410；它的程序不会为整机新增 USB Host 控制器。
