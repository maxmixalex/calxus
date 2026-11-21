# Calxus

当前状态：文档、可复现固件构建及原理图引脚核对已完成；PCB 正在生成与检查中，尚未作为制造就绪版本发布。板外形为 80×42 mm，外壳包络为 86×48×19 mm。

Calxus 是 USB 总线供电的计算器连接转换器，采用 CH444G 四档硬件选择，将一条上行 USB-C 数据连接送到原生 Mini-B、USB-A、TI SilverLink 或 CH343P 串口。TI 双线端使用 TUSB3410 与外部 24LC64；串口端机械选择 CASIO 尾线或带防呆接口的 HP / TI-Nspire AUX 尾线。

日常传输使用计算器原有软件或 WebTILP，不新增运行时上位机。四种 USB 路径每次只选一种；原生路径不经过 USB Hub。转换器本身可通过外部 EEPROM 重编程与恢复，具体方法见固件文档。

| `S1 S0` | 路径 |
|---|---|
| `00` | 原生 Mini-B |
| `01` | USB-A |
| `10` | TI SilverLink |
| `11` | CH343P UART，再选 CASIO / AUX |

本轮已在 SDCC 4.2.0 实际构建 SilverLink 参考程序，5120 字节程序的 SHA-1 与上游一致，并验证完整 8192 字节 EEPROM 镜像格式。硬件制造、实物烧录、各计算器传输和功耗项目须依照验证表完成，不能从固件构建成功推定整机已通过。

- [使用说明](docs/user-guide.zh-CN.md)
- [软件兼容范围](docs/software-compatibility.zh-CN.md)
- [装配与首板调试](docs/assembly-and-bringup.zh-CN.md)
- [转换器固件、烧录与恢复](firmware/README.md)
- [验证记录](docs/validation-record.zh-CN.md)
- [独立电气核对](docs/electrical-crosscheck.zh-CN.md)
- [技术来源](docs/sources.md)
