# HP 与 TI-Nspire 尾线

Calxus 的 AUX 是受保护的 3.3 V UART 通道。计算器端的专用插头由尾线适配；不把外形相似的 Mini-B、HP mini-serial 或 Nspire dock 当成同一种接口。

## 板端定义

下表中的 RX/TX 始终以 Calxus 为参照。板上 J6 针号是最终依据，线侧观察方向可能相反。

| J6 针号 | 板上网络 | 尾线去向 |
|---|---|---|
| 1 | GND | 计算器信号地 |
| 2 | AUX_RX | 计算器 TX |
| 3 | AUX_TX | 计算器 RX；板端为保护后的开漏发送 |
| 4 | NC | 留空，不接计算器电池或供电触点 |

电脑使用 CH343 的现有串口驱动和目标软件。AUX 与 CASIO 通过 J7 两组跳线成对选择，具体短接位置见[装配说明](assembly-and-bringup.zh-CN.md)。

## HP 39gs

HP 原厂《39gs User’s Guide》19-4 页区分了两个接口：计算器之间使用专用四针 mini-serial；PC Connectivity Kit 使用五针 Mini-USB。Calxus 的 `00 MINI` 原生 USB 路径保留后者的设备协议和驱动。因此，39gs 的常规电脑连接可以直接使用 Mini-B 尾线，不依赖 AUX 的串口针序。

手册 19-5 页还列出 USB 和串口传输选项，但没有给出 mini-serial 的逐针电气定义。Calxus 已提供 AUX 板端适配接口；本版没有把未经一级来源或实物确认的 39gs 插头针序写入已验证尾线清单。HP 50g 的专用电平和关闭时 RX 驱动行为有原设计者说明，这些资料不能单独作为 39gs 针序已经一致的证据。

来源：[HP 39gs 原厂手册，19-4～19-6 页](https://literature.hpcalc.org/official/hp39gs-ug-en.pdf)、[HP 原厂 Mastering 指南，第 226、240 页](https://literature.hpcalc.org/official/hp39gs40gs-mastering-en.pdf)、[HP 50g 串口线原设计说明](https://commerce.hpcalc.org/serialcable.php)。

## TI-Nspire dock UART

Hackspire 的硬件研究页给出了 **CX II 底部 26 针 dock** 的信号表，并明确 UART 使用 TTL 电平。下面是该特定表的信号映射，不是所有 Nspire 版本共用的插头机械图。

| CX II dock 信号 | 研究页针号 | Calxus J6 |
|---|---:|---:|
| GND | 5、8 或 22 | 1 |
| 计算器 TX | 23 | 2 |
| 计算器 RX / GPIO19 | 24 | 3 |
| VCC、USB 电源及其他触点 | 其他 | 不连接 |

研究页定义的观察方向是计算器翻到背面、接口位于下方，左侧为第 1 针；制作实体插头仍需对照该页图片和机器实际朝向。端子常用设置为 115200 bit/s、8 数据位、无校验、1 停止位、无流控。启动日志可用现有串口终端读取，计算器普通文件管理继续使用原生 USB。

该资料没有给出各代机器统一的精确 UART 电压保证。首次接入具体机器时，只接 GND 与计算器 TX，先核对空闲电平及日志，再决定是否接入发送端。低于本板输入门限的机型需要对应电平适配，不得把固定 3.3 V 的 AUX 直接标为所有 Nspire 硬件版本通用。

来源：[Hackspire：J01 dock 与 UART](https://www.hackspire.org/Hardware/#uart)。该页面还包含其他板内调试连接器，它们的针号不能替代这里的 J01 dock 针号。
