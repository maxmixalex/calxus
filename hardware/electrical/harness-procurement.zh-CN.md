# 线束与非 SMT 采购清单

本表补充板上 BOM。尾线、公头、压接端子、护套与上行数据线不属于 SMT 贴片器件；J3/J4/J5 只借用连接器焊盘，不能把焊盘库型号当作尾线采购料号。下列库存来自 **2026-11-21 08:17–08:25 UTC** 的立创商品详情实时回读，不是未来库存或交期承诺。没有下单。

| 用途 | 每台用量 | 型号与立创链接 | 实查库存 / 起订 | 装配决定 |
|---|---:|---|---|---|
| Mini-B 尾线兼 TI/CASIO 线材 | 1 条成品线 | Ckmtw **S002020047 / [C430897](https://www.lcsc.com/product-detail/C430897.html)** | 136 条 / 1 条 | USB-A 公→Mini-B 5针公，1.5m；保留 Mini-B 端约0.25–0.30m，余料裁两段0.20–0.30m作 TI/CASIO 线材 |
| TI 2.5mm TRS 公头 | 1 个 | CUI / Same Sky **SP-2533A / [C4992833](https://item.szlcsc.com/5567705.html)** | **0 个 / 1 个；需补货** | 2.5mm、三极、焊线式、带圆形外盖；原厂图已核 |
| CASIO 2.5mm TRS 公头 | 1 个 | 同上 **SP-2533A / C4992833** | **0 个；需补货** | 独立尾线，标注 CASIO |
| AUX 线端壳 | 每条 AUX 线 1 个 | JST **PHR-4 / [C111514](https://www.lcsc.com/product-detail/C111514.html)** | 45,300 个 / 50 个 | 原厂 PH 系列4位2.0mm壳，配板端 B4B-PH-K-S |
| AUX 压接端子 | 装3个，另备1个 | JST **SPH-002T-P0.5S / [C111515](https://www.lcsc.com/product-detail/C111515.html)** | 2,770,700 个 / 100 个 | 适用30–24AWG、绝缘外径0.8–1.5mm，只装1/2/3位 |
| AUX 多股导线来源 | 每条 AUX 线 1 组 | BXCONN **PH4P-26AWG-200-A1T / [C53413426](https://www.lcsc.com/product-detail/C53413426.html)** | 100 组 / 5 组 | 200mm、UL1007 26AWG、7×0.16mm镀锡多股、单芯绝缘Ø1.3mm；剪除第三方壳和端子，选3根重压接原厂 JST 端子 |
| PC USB-A 上行数据线 | 使用时1条 | Ckmtw **S100920007 / [C430908](https://www.lcsc.com/product-detail/C430908.html)** | 84 条 / 1 条 | USB-A 公→USB-C 公，1m；图纸有 D±、22AWG电源、28AWG信号、Type-C插头内56kΩ CC电阻；也可用已有合格数据线 |
| 护套、热缩管、标签 | 1 组 | 按下述实际尺寸采购 | 通用耗材，未锁定单一商城料号 | 标记 TI/CASIO/USB/AUX；焊点独立绝缘；AUX夹持段必须有外护套 |

**当前不能称整机线材全部现货。** 立创确有正确的2.5mm TRS公头目录，但实查 SP-2533A（C4992833）和 SP-2501（[C4992470](https://item.szlcsc.com/5567342.html)）均为0库存。SP-2501 原厂也确认三极、可焊线、带应力释放，可作为补货候选，装配尺寸需随实物复核。另查 Tensility 50-00400 / C19856694 也为0库存，属于需包胶处理的候选，不能直接替代带壳首选。商城“相似料”中的 SP-3533-02 是3.5mm，不能替代；四极 TRRS、单声道 TS 和2.5mm母座也不能替代。这是已核型号的库存缺口，不声称穷尽商城全部目录。

补充在 **2026-11-21 09:12–09:16 UTC** 按限定范围直接读取5款有效2.5mm TRS公头商品页（含首选复核），结果如下。原厂页逐一核实为2.5mm、三极、公头；库存只取立创当前商品页，不借用其他经销商库存。

| 本次候选 | 立创型号 | 当前库存 | 装配性质 |
|---|---|---:|---|
| Same Sky SP-2533A | [C4992833](https://item.szlcsc.com/5567705.html) | 0 | 带壳焊线式，继续作为已核首选补货项 |
| SCHURTER 4831.1310 | [C4992735](https://www.lcsc.com/product-detail/C4992735.html) | 0 | 带绝缘壳的焊线式三极公头 |
| Tensility 50-00400 | [C19856694](https://www.lcsc.com/product-detail/C19856694.html) | 0 | 供包胶用插头芯，不能冒充完整带壳公头 |
| SCHURTER 4831.1300 | [C4991788](https://www.lcsc.com/product-detail/C4991788.html) | 0 | 带屏蔽壳的焊线式三极公头 |
| Same Sky SP-2533-01 | [C4992651](https://www.lcsc.com/product-detail/C4992651.html) | 0 | 供包胶用插头芯，不能冒充完整带壳公头 |

本次5款有效候选均未找到明确现货，也未确认可裁作两条尾线的现货2.5mm TRS完整线。因此**两只2.5mm TRS公头仍是采购缺口**，不改成3.5mm或二极/四极替代，也不声称已穷尽商城。具体产品字段、原厂验证链接、范围与时间记录在 [2p5-trs-stock-check-20261121.json](2p5-trs-stock-check-20261121.json)。PCB、EP钢网与已审核布线保持冻结。

补查现货成品线和双公线裁尾方案：2026-11-21 对立创公开音频线目录及定向关键词检索，目录显示的6条成品线均无库存，本轮也未建立“真实2.5mm三极公头 + 原厂规格 + 现货C号”同时成立的替代项。原厂确有2.5mm立体声公头到裸线产品，但未核得其立创现货来源，因此没有加入采购表。这个有限范围的补查保留原缺口，不声称商城完全没有可用品，见[成品线补查记录](2p5-trs-cable-check-20261121.json)。

C430897 原厂图纸 S002020047、版本A、日期2012-11-01，线材为 **UL2725，28AWG一对 + 28AWG两芯 + 铝箔 + 64编织，黑色外径Ø3.8mm**。导通表明确 USB-A 的1/2/3/4接 Mini-B 的1/2/3/5，Mini-B pin4 ID不接，编织连接两端外壳。四根绝缘芯都是28AWG，不把它描述成24AWG电源线。截短后的压降与数据完整性仍按首板测试验收。

一条1.5m线分配给三条固定尾线：先按 Mini-B 目标外露长度加壳内余量截取，再从余料裁 TI、CASIO 各一段。USB-A 插头及靠近它的磁环不装入 Calxus。慢速尾线取三根绝缘芯，第四根两端分别绝缘；编织仅在桥板端接 GND，计算器端剪短绝缘，信号地仍由独立芯线接 TRS Sleeve。SP-2533A 出线孔Ø4±0.5mm，与Ø3.8mm线材名义匹配；到货后验证穿线、夹持与弯折，不强塞、不削破外被。机械固定尾线夹为Ø3.6mm孔，对Ø3.8mm外被提供0.2mm名义压缩，首件确认不伤线、不滑脱。

AUX 默认用原厂 JST PHR-4 壳与 SPH-002T-P0.5S 端子。C53413426 仅作已核多股导线来源，不默认第三方连接器与 JST 的配合已经验证。去掉原压接件，以黑/白/黄或其他清楚标识的三根线重新压接，通断确认后装入1/2/3位，第4位留空。夹持段加热缩/软护套，成品外径目标 **2.9–3.1mm**，配机械Ø2.8mm夹孔，不能直接夹散线。对端特殊插头按具体机型查验 [AUX 适配说明](../../docs/aux-adapters.zh-CN.md)。

| 板端 | 对应公头接点 |
|---|---|
| J3.1 VBUS | Mini-B pin1 VBUS |
| J3.2 D− | Mini-B pin2 D− |
| J3.3 D+ | Mini-B pin3 D+ |
| J3.4 NC | Mini-B pin4 ID留空；不接地 |
| J3.5 GND | Mini-B pin5 GND |
| J3.6 Shield/GND | 屏蔽编织/公头屏蔽壳 |
| J4.1 / J4.2 / J4.3 | TI Tip / Ring / Sleeve |
| J5.1 / J5.2 / J5.3 | CASIO Tip（计算器TX→桥RX）/ Ring（桥TX→计算器RX）/ Sleeve |
| J6.1 / J6.2 / J6.3 / J6.4 | GND / bridgeRX / bridgeTX / NC |

用通断表确认接触面，不能只按线色；焊接面图与配合面图相反。CASIO 不额外串接已交叉的 SB-62 线。AUX 计算器TX接J6.2、计算器RX接J6.3，端子4不接电池电压。焊点不能承受拉力，壳内保留弯曲余量。

Mini-B 的屏蔽与绞对保留到尽量靠近板端，剥线分离长度目标≤5mm。S100920007 图纸证明有数据接线和56kΩ CC电阻，但没有给出90Ω线缆阻抗、屏蔽结构或480Mbps认证；它是已落实商城料号的数据线候选，最终高速验收必须使用目标线缆测试。板上受控阻抗不能替代整机 USB 眼图、协议及软件传输验证。

原厂依据：

- [C430897 / S002020047 原厂图](https://datasheet.lcsc.com/datasheet/pdf/4be3348a50351aa811fbe41e427c005c.pdf?productCode=C430897)：接口、1.5m、线材、Ø3.8mm、针序。
- [SP-2533A 原厂图](https://atta.szlcsc.com/upload/public/pdf/source/20240126/33F9219FFB7CC6459161E3ED74553172.pdf)：三极、Ø2.5mm、27.7mm长、外盖Ø8mm、出线孔Ø4±0.5mm。
- [SP-2501 原厂页](https://www.sameskydevices.com/product/interconnect/connectors/audio-connectors/audio-plugs/sp-2501)：三极2.5mm、可焊线、应力释放。
- [JST PH 原厂手册](https://www.jst-mfg.com/product/pdf/eng/ePH.pdf)：PHR-4、SPH-002T-P0.5S、AWG与绝缘外径范围。
- [C53413426 原厂图](https://datasheet.lcsc.com/datasheet/pdf/f0b3581107d676cb7669dbba4685bc34.pdf?productCode=C53413426)：UL1007 26AWG、7×0.16mm、Ø1.3mm、200mm。
- [C430908 原厂图](https://datasheet.lcsc.com/datasheet/pdf/87deec2addefe4b7731637ed71cc524c.pdf?productCode=C430908)：USB-A→C、1m、四芯与56kΩ CC电阻。

库存、MOQ、来源URL与原厂图 SHA-256 见 [harness-procurement.json](harness-procurement.json)。长度、剥线、套管、夹持尺寸是项目装配决定，不是元件厂的测试结论。
