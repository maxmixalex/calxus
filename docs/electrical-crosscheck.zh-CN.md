# 独立电气核对记录

日期：2026-11-21。对象是最终 CH444G 四档版本，核心 PCB 80×42 mm、外壳 86×48×19 mm。审查输入为 `calxus_design_input.json` 的 D16 修订版：120 个位号、69 个有名网络，其中 23 个 TP 为仅 PCB 测试焊盘，原理图范围为 97 个器件。

本次逻辑审查通过；脚本结果见 [electrical-contract.json](../validation/electrical-contract.json)。它记录输入文件 SHA-256、与放置坐标无关的逻辑引脚表 SHA-256、逐项结果和实际推导的开关状态。该结论针对设计输入，不能代替实际 EDA 网表等价检查、PCB 连通检查或样机实测。

## 核对依据和方式

先读取器件手册的真实引脚用途，再与设计输入逐项比较。检查器不直接采用输入文件中的档位结果，而是用 Alps SSSS224100 官方触点表、D11–D15 的实际阳极/阴极方向推导选择码和供电使能。USB-C 的合并触点、TUSB 的裸露焊盘 33、CH343P 的裸露焊盘 17 则按本工程实际嘉立创库几何核对；原理图符号内部 UUID 不当作物理引脚号。

| 项目 | 核对结果及实际含义 |
|---|---|
| USB-C | A6/B6 同为 D+；A7/B7 同为 D−；CC1/CC2 各自 5.1 kΩ 到地；VBUS 与 GND 分组符合实际库；SBU 未接 |
| CH444G | YA/YB 为上行 D+/D−；四对输出依次 native、A、Silver、UART；15 脚 NC；EN# 低有效 |
| USB 供电 | 三颗 TPS2552DBVR 的 IN1/OUT6、低有效 EN3、GND2、FAULT4、ILIM5 对应正确；只有当前外部支路或串口支路被启用 |
| TUSB3410 | 3/25 脚为 3.3 V，4 脚为内部 1.8 V，8/18/28/33 接地；USB 6=D+、7=D−；TEST0/TEST1/SIN 有上拉 |
| TI 双线 | P3.3/30 脚到 Tip、P3.4/29 脚到 Ring。NPN 发射极为 GPIO、集电极为计算器线；并联肖特基阳极在 GPIO、阴极在计算器线，与 SilverLink B 参考电路一致 |
| TUSB 挂起 | D10 阳极 VREGEN、阴极 SUSPEND；15 kΩ、32.4 kΩ 与复位电容连接符合 TI 总线供电建议。90.9 kΩ/100 kΩ 保持分压理想空载值约 1.729 V，不能把肖特基低电平压降误当成 1.8 V 电源 |
| CH343P | VDD5/VBUS 在 5V_SERIAL，VIO 为 3.3 V，V3 只按手册去耦；USB 7=D+、8=D−；EP=17 接地；未用脚明确 NC |
| UART | TX 用 SN74LVC1G07 非反相开漏，RX 用 SN74LVC1G17 非反相缓冲。J7 同时选 RX/TX，CASIO/AUX 不并联；CASIO 直插公头 Tip=计算器TX、Ring=计算器RX，与原作者实测接法一致；J6 第 4 针 NC |
| UART 掉电反灌 | D16 阳极 3V3、阴极 UART_PULLUP；R28/R31 从该隔离节点上拉，阻断尾线经上拉电阻回到关闭的 3V3 电源。输入/输出缓冲还依赖自身 Ioff 能力；实际漏电待测 |
| EEPROM | 24LC64 A0/A1/A2 接地，地址 0x50；J9 单独可断 SCL。J8 依次为 EE_VCC、GND、EE_SCL、EE_SDA、EE_WP、SIL_RESET。J10 短接允许写入；R23/R25 可在断电时隔离 SDA/EEPROM 电源 |
| 网络完整性 | 所有有名网络至少有两个节点；关键 NC 和电源节点逐脚检查；电容均有地回路且两端不在同一网络。该检查不证明实际铜线已经完成 |

## 四档状态推导

| SW1 档位 | 官方触点闭合 | IN1 IN0 | CH444 数据对 | 唯一启用的电源 |
|---|---|---|---|---|
| NATIVE | 1–3，6–8 | 00 | USB_NATIVE_DP/DM | VBUS_NATIVE |
| USB-A | 2–3，7–8 | 01 | USB_A_DP/DM | VBUS_USBA |
| SILVER | 3–4，8–9 | 10 | USB_SIL_DP/DM | 5V_SERIAL |
| UART | 3–5，8–10 | 11 | USB_UART_DP/DM | 5V_SERIAL |
| 两刀均开路的间隙 | 无 | 11 | EN# 高，数据断开 | 无 |

5V_SERIAL 同时供给 TUSB3410 和 CH343P，CH444 只选择其中一个数据接口。表中的开路间隙模型不覆盖两个机械刀片的偏斜、触点反弹与电源建立时间，因此使用说明要求拔下上行 USB 后切档；不能据此宣称已验证带电无缝切换。

## 审查中已落实的修正

1. 最终 BOM/引脚表加入 D16 后，发送高电平按实际二极管上拉写成约 3.0–3.2 V；接收和发送的逻辑域仍是 3.3 V。目标输入阈值、线缆电容和 115200 波特率下的上升沿须实测。
2. 首次上电步骤已与分支电源一致：原生/A 档检查串口电源关闭，断电切到 Silver 档后才测 3.3 V、TUSB 1.8 V、复位和晶体。旧步骤在原生档期待 TUSB 起振已删除。
3. 暴露焊盘按实际库使用 TUSB 33、CH343P 17；没有继续使用资料图中的 EP/0 字符直接接网。
4. EEPROM 恢复使用可拆的 J9 SCL 跳帽；外部独立编程同时隔离 R23 与 R25，避免向掉电主板反供电。WP 只保护写入，不能绕过读取旧镜像。

## 电流与反向电流边界

从本次实际重建的 5120 字节固件中读出配置描述符模板：`bMaxPower = 0x32`，即 100 mA；VID/PID 为 0451:E001。见 [离线描述符检查](../firmware/validation/descriptor-inspection.json)。这不是主机枚举抓包。40 mA 是串口支路普通工作设计预算，需测整机而非只看单颗芯片电流。

226 kΩ 的串口限流设置约为 101.3/120.0/142.1 mA（最小/典型/最大）；52.3 kΩ 的两个原生输出支路约为 448.3/501.6/562.4 mA。它们是故障限制，不能当作主机授权的可用电流。USB 设备配置前、配置后及挂起时分别按对应主机和设备要求验收，外部设备的充电也计入预算。

TPS2552 反压保护不是理想二极管：本次手册电气表给出 95–190 mV 的反压判定阈值及 3–7 ms 的关闭响应，期间可能出现反向电流。原生尾线应连接设备角色，USB-A 不接另一台供电主机。掉电反灌、未选桥接芯片的挂起状态、整机挂起总电流、浪涌和 VBUS 压降仍列入实物验收，尚未记为通过。

## 实际 EDA 输出比较

比较器为 [compare_netlists.py](../tools/compare_netlists.py)。默认 `--scope schematic` 明确排除输入里标记 `pcb_only` 的 23 个 TP；其余 97 个器件必须与实际原理图导出的物理引脚号、网名和整个同网引脚组一致。`--scope pcb` 则包含全部 120 个位号及测试焊盘。

```sh
python tools/check_electrical_contract.py path/to/calxus_design_input.json --output validation/electrical-contract.json
python tools/compare_netlists.py --scope schematic --design path/to/calxus_design_input.json --actual path/to/actual-schematic-netlist.json --output validation/schematic-netlist-comparison.json
python tools/compare_netlists.py --scope pcb --design path/to/calxus_design_input.json --actual path/to/actual-pcb-netlist.json --output validation/pcb-netlist-comparison.json
```

实际嘉立创最终原理图导出已独立比较通过：97 个器件、344 对物理引脚/网络均一致，网名及完整同网引脚组同时匹配。见 [原理图比较记录](../validation/schematic-netlist-comparison.json)。原始导出 SHA-256 为 `e6d58ba176c7d3b843c184bf627a4be0540f0e4156bfabd702182b28c6d4b9e6`。U2.31/.32 的同网 TP 在 PCB 范围，故原理图中各只有一个节点是预期情况。

最终导出的 97 个器件已逐项另核对 Device、Footprint、Supplier Part 非空，且 Supplier Part 与审查输入相符；U2/U3 的早期库关联缺失已经修复。主工程原生操作已回读全部 NC 标志为 true。实际原理图 ERC 导出无 error/fatal，保留两条 `SHOWDANDLING` warning，对应 U2 未分配 GPIO `TP_GPIO30/31` 的原理图单节点；它们分别接到 PCB-only 的 TP20/21。见 [ERC 与库关联记录](../validation/schematic-erc-summary.json)。这里没有把“无错误”写成“零警告”。PCB 网表、实际铜连接与 PCB DRC 尚待完成。文件格式不受支持时脚本报错，不能通过猜测字段把空输入当作成功。NC 可以在导出中省略或成为独立未连接节点，但不能与其他引脚同网。报告检查命名及连通分组，仍须另做 PCB 实际布线连通、DRC、封装焊盘和机械装配检查。

依据：TI TUSB3410 SLLS519J（引脚、图 6-11）；WCH CH440 系列本次实际下载版本 3E（§4.4、逻辑门限）；CH343 v2.0（引脚、电源、挂起）；TI TPS2552 SLVS841G（DBV 脚位、反压保护、限流）；Alps SSSS224100 官方电路图；SilverLink B 参考原理图；SN74LVC1G07/17 数据手册。原始链接见[技术来源索引](sources.md)。
