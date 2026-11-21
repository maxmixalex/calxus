# Calxus

Calxus RevA / r7 的可编辑嘉立创工程、原生三页原理图 PDF、实际 Gerber、SMT BOM/CPL 和机械文件已生成并独立核对。PCB 为 80×42 mm，外壳包络为 86×48×19 mm。

**当前作为完整工程审核包交付，制造放行仍为 `false`。** 实际 CAM 的 247 个孔/槽、四层铜、板框、QFN 钢网和指定过孔阻焊均通过；原生 PCB 检查为 0 飞线、0 连接/净距/物理错误，但原始 DRC 仍有 4 项：3 项已审查的总线段长度统计例外，以及 1 项尚未解释的全局 `Netlist Error`。独立网表一致不能消除这条原生错误。完整结果、文件哈希和剩余条件见[发布验收汇总](validation/release-summary.json)。

| 交付入口 | 内容 |
|---|---|
| [Calxus_RevA.epro2](hardware/native/Calxus_RevA.epro2) | 实际保存、重新打开和导出的完整原生工程 |
| [Calxus_RevA_schematic.pdf](hardware/schematic/Calxus_RevA_schematic.pdf) | 当前 J2 版本的三页 A2 图框原生 PDF，已逐页看图；原生导出含额外页面边距 |
| [Calxus_RevA_Gerber.zip](hardware/manufacturing/Calxus_RevA_Gerber.zip) | 未改写的实际制造导出；[独立 CAM 验收](validation/native-final-gerber/gerber-validation.json) |
| [SMT BOM](hardware/manufacturing/Calxus_RevA_SMT_BOM.csv) / [SMT CPL](hardware/manufacturing/Calxus_RevA_SMT_CPL.csv) | 本次原生导出筛选的 87 件贴装器件、34 行采购分组，保留原生 Mid 坐标 |
| [机械文件与装配说明](mechanical/README.md) | 七种打印件及源设计派生总装；93 件实装模型、247 孔和 16 个选档姿态已核对 |

Calxus 是 USB 总线供电的计算器连接转换器，采用 CH444G 四档硬件选择，将一条上行 USB-C 数据连接送到原生 Mini-B、USB-A、TI SilverLink 或 CH343P 串口。TI 双线端使用 TUSB3410 与外部 24LC64；串口端通过 J7 两只跳帽成对选择 CASIO 尾线或带防呆接口的 HP / TI-Nspire AUX 尾线。调整跳帽前断开 USB 并打开外壳。

日常传输使用计算器原有软件或 WebTILP，不新增运行时上位机。四种 USB 路径每次只选一种；原生路径不经过 USB Hub。转换器控制固件可通过外部 EEPROM 重编程与恢复，详见固件文档。

| `S1 S0` | 路径 |
|---|---|
| `00` | 原生 Mini-B |
| `01` | USB-A |
| `10` | TI SilverLink |
| `11` | CH343P UART，再由 J7 选择 CASIO / AUX |

现行原理图为 97 个器件、345 个逻辑引脚和 21 个显式 NC；PCB 包含 23 个额外测试焊盘。板上实装 87 个 SMT 和 6 个手焊通孔器件，共 93 件；J3/J4/J5/J8 四组接口不装库中的连接器，作为焊线或服务焊盘使用。USB-A 母座 J2 使用 `C456017`（AF 10.0 HC6.3 弯插款），独立屏蔽固定脚 5、6 均接地。

SilverLink 参考程序已用 SDCC 4.2.0 实际构建两次，5120 字节程序 SHA-1 与上游一致，完整 8192 字节 EEPROM 镜像格式通过。实物 PCB 制造、EEPROM 烧录、各计算器传输、功耗和信号完整性尚未测试。机械总装是基于真实器件模型和保存源生成的可复核装配，不能代替打印与试装。

- [使用说明](docs/user-guide.zh-CN.md)
- [软件兼容范围](docs/software-compatibility.zh-CN.md)
- [装配与首板调试](docs/assembly-and-bringup.zh-CN.md)
- [转换器固件、烧录与恢复](firmware/README.md)
- [验证记录](docs/validation-record.zh-CN.md)
- [独立电气核对](docs/electrical-crosscheck.zh-CN.md)
- [嘉立创原生工程与导出格式](docs/native-project.zh-CN.md)
- [制造文件与工艺说明](hardware/manufacturing/README.md)
- [技术来源](docs/sources.md)

本版计算器兼容性尚未实机验证；AUX 只覆盖已核对电平和针序的具体机型。两只标准 2.5 mm TRS 公头的现货采购缺口仍保留，不能由板上 BOM 齐备推定整机配件已齐备。历史候选与诊断快照用于追溯；上表是本次交付的统一入口。
