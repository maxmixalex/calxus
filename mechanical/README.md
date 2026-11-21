# Calxus R1.2 机械设计

本目录提供实际可编辑的参数化 CAD 源码、FreeCAD 工程、STEP 装配、分件 STEP、打印 STL、机械接口 JSON、板框 DXF、装配图及几何校验报告。外壳为两片式螺钉结构；右端四条固定尾线由两片 TPU 线夹及渐缩护套支撑；顶部滑钮通过有导向的打印拨叉驱动 ALPS 四挡开关。没有电池、显示屏或额外存储机构。

版本为 **R1.2-ADJUSTABLE-PROTOTYPE**。所有 CAD 几何已经生成并进行数字校验；尚未打印实物，未做拉力、插拔寿命、热或电气试验。USB 插座的 XY 保留包络来自本项目选中的实际 EDA 库封装和已锁定的放置坐标；它们不是厂商认证的三维实体。USB-A 已更换为原厂图确认的 C456017 短体卧式插座；r7 的93实装模型已通过壳体干涉检查，最终原生板体已确认 J2 孔径和槽方向正确；批准的 J2 模型高度修正在源设计总装中通过配合检查。首件夹持试验仍须实测。三路线径已按 C430897 原厂图的 Ø3.8 设定。不要把参考插座包络模型当成供应商的完整 3D 模型。

## 打开与打印

- [calxus_enclosure.FCStd](output/calxus_enclosure.FCStd)：FreeCAD 原生分件工程，含接口参数表。零件为交换实体；完整参数化重建源为 Python 和 JSON。
- [calxus_assembly.step](output/calxus_assembly.step)：装配交换文件，包含真实壳体、线夹、滑钮、板体和明确标为 `REFERENCE` / `ENVELOPE` 的参考件。滑钮展示在 0 挡。
- [打印 STL 文件夹](output/)：已经调整到推荐打印方向，最低面 Z=0。选取两片壳体、两片 TPU 线夹、拨叉和指拨件；尺寸试片另选 `calxus_fit_coupon.stl`。
- [calxus_mechanical_drawing.pdf](output/calxus_mechanical_drawing.pdf)：五页装配、接口、材料、可调滑钮剖面和检验图。
- [mechanical_contract.json](mechanical_contract.json)：共享 EDA / CAD 接口。修改端口坐标前先更新此文件，再重建 CAD。

**装配来源区分：** 本目录同时保留机械参考装配与已完成的源设计实装总装，文件名、图内标题和报告均区分来源。

- [calxus_source_assembly.step.gz](output/calxus_source_assembly.step.gz) 是**按最终设计源生成**的 93 器件整机 CAD，含 6 个安装用打印件、真实板体、93 个实装器件模型和 14 个螺钉／嵌件／热缩圈参考对象，共 114 个命名对象。它采用已有 r7 原生真实模型，保留其位置和旋转，仅按已批准的候选源将 J2 模型上移 0.10；J3/J4/J5/J8 四个不安装的库连接器模型被省略。
- [真实器件爆炸预览](output/calxus_source_assembly_exploded.png) 与 [93 器件板卡预览](output/calxus_source_pcba.png) 均直接渲染上述 BREP 模型，图内标为 `SOURCE-DERIVED`；不是安装包络方块。颜色用于区分类别，不是对厂商材料或表面处理的认证。
- [calxus_source_board.step.gz](output/calxus_source_board.step.gz) 保留原生已验证的外轮廓和 1.606203 厚度，舍弃全部旧内孔后按最终候选的 56 PAD 孔、189 VIA 孔及 J1 两个定位孔重建，共 247 个名义钻削特征。四个 EP VIPPO 的填孔／盖铜和单独的铜、阻焊薄层没有拆成额外实体；此板体模型不代替加工文件。
- `calxus_assembly.step`、FreeCAD 工程、原两张机械预览及五页 PDF 仍是机械参考装配，接口代理和器件包络在文件和图内标明。它们用于打印结构与尺寸审查。

源设计总装的 [完整来源清单](validation/calxus_source_assembly-manifest.json)、[实体配合报告](validation/source-derived-pcba-fit.json)、[247 孔校核](validation/source-derived-board-geometry.json)、[16 姿态运动检查](validation/source-derived-selector-motion.json) 和 [独立 STEP 回读](validation/source-derived-assembly-roundtrip.json) 已实际生成。来源绑定于 [候选工程](../hardware/native/Calxus_RevA_candidate.epro2) 的明确机械输入快照；具体候选 SHA、仅铜修改的等价证明或过孔变更后的重新切板记录，以来源清单为准，不能把较早快照称为最终原生输出。93 器件与板、壳体、紧固件和相邻器件没有超过报告阈值的交叠，全部 114 个装配对象及 247 孔通过回读；七个打印设计的 14 个 STEP/STL 文件保持冻结。[最终机械版本记录](validation/source-derived-final-revision.json) 对照前版，明确记录唯一一处过孔位置／孔径变更与其后的完整重新计算。交换文件共享 20 个原生模型定义、保留 93 个器件实例及完整 3D 曲面和 2D 修剪参数曲线；gzip 为无损压缩，解压后的 STEP 字节已核对一致。没有通过减面、删件或尺寸近似缩小文件。

**机械数字发布验收已完成，规范整机 CAD 保持 `SOURCE-DERIVED`，本交付包未采用或验证新的原生完整 PCBA STEP。** [机械发布验收记录](validation/mechanical-release-acceptance.json) 将完整总装回读、实际最终原生工程、实际板体 STEP 和实际 CAM 连接到明确文件哈希；其中 `mechanical_release_accepted=true`、`fresh_native_full_pcba_exported=false`。 后一个字段只描述本次发布并核验的机械包：本机另存有可选的 fresh full-PCBA 导出，但未传输、未采用、未独立核验；不表示本机没有该可选文件。这项机械验收不替代电气功能或实物首件试验。

[最终原生源等价对照](validation/native-final-mechanical-source-equivalence.json) 确认 97 个器件／模型绑定和全部非 VIA 机械记录完全一致；189 个 VIA 一一对应，128 个新增孔只发生原生 ID 重建及四位小数 mil 保存规范化，最大中心差 0.000001636。全部 56 PAD 孔、J1 两个定位孔和 189 VIA 已由 [实际最终 CAM 报告](../validation/native-final-gerber/gerber-validation.json) 核对通过。

[实际最终板体 STEP](validation/Calxus_RevA_final_board.step.gz) 与 [实体测量记录](validation/native-final-board-representation.json) 确认厚度 1.606203、J2 四个 Ø1.0 信号孔及两个 2.1×0.8 的 Y 向槽正确。该板体 STEP 只生成 58 个非 VIA 孔，189 个 VIA 名义钻孔位置仍是实体；规范源设计板体保留全部 247 个名义加工特征。两者外轮廓挤出板坯的双向布尔差为 0，均有四个圆弧。实际 GKO 也有四段 R1 圆弧；[轮廓命令记录](../validation/native-final-gerber/outline-corners.json) 说明左下角斜弦仅为 Gerbonara 预览填充限制，加工文件未改动。无需为 STEP 的表示范围或预览效果重建已验收 CAD。

[assemble_actual_pcba.py](assemble_actual_pcba.py) 保留原来的严格门槛，仍会拒绝把较早 r7 原生钻孔／安装面诊断当成新的原生全装配通过。源设计生成器是另一个独立文件 [assemble_source_pcba.py](assemble_source_pcba.py)，没有放宽该门槛。

本精简目录的分件 STEP 使用装配坐标；STL 仅保留带 `_print` 后缀的打印方向版本，均为底面 Z=0。试片本身已经位于打印方向，因此保留 `calxus_fit_coupon.stl`，没有重复的普通装配坐标 STL。 试片只测未改变的 Ø2.9/3.0/3.1 热熔嵌件孔、1.9×2.0 拨叉槽及 TPU 线孔，不代表新版导向端柱、校准螺钉槽或完整四挡行程验收；后三项用实际打印的顶盖、指拨件和拨叉组装检查。拨叉和指拨件分件以行程中心为建模基准，装配 STEP 则平移到 0 挡。不要通过切片软件的整体缩放修正孔径或配合。

## 固定接口

单位均为 mm，右手坐标。PCB 左下角底面为 `(0,0,0)`，板长沿 X、板宽沿 Y、板厚沿 +Z。

| 项目 | 数值 |
|---|---|
| PCB | 80 × 42 × 1.6，圆角 R1 |
| 安装孔 | 4 × Ø2.2 NPTH；(3.5,3.5)、(76.5,3.5)、(3.5,38.5)、(76.5,38.5) |
| 安装禁布区 | 每个孔中心 R3.0，PCB 正反面都保留 |
| 刚性外壳 | X −3…83，Y −3…45，Z −4.5…14.5，即 86 × 48 × 19 |
| 带指拨件总高度 | 21.9；指拨顶面 Z17.4 |
| 包含 USB-A 悬伸的 Y 总宽 | 49.925；插口前缘约 Y−4.925，壳前表面 Y−3 |
| 线夹及渐缩护套 | 外端 X96.5；外壳到护套端的刚柔组件总长 99.5 |
| PCB 下方预留高度 | 1.8；到内底板余量 0.7；93 实装器件最低 1.394；1.794 为不安装的库尾线座模型 |
| PCB 上方预留高度 | 8.6；普通顶盖余量约 2.294；实际原生高排针为 8.5，导轨区域另验 |
| USB-C J1 | TYPE-C-31-M-12 / C165948，EDA 锚点 (4.22,21)，270°，朝 −X |
| USB-A J2 | SHOU HAN AF 10.0 HC6.3 / C456017，EDA 锚点 (40,4.074980)，0°，朝 −Y |
| SW1 | ALPS SSSS224100 / C255514，封装中心 (20,34)，0°，侧拨杆朝 −Y |
| 顶部滑槽 | 中心 (20,30.9)，11.2 × 3.3；X 总行程 6，挡间距 2 |
| 外壳结合缝 / 尾线中心 | Z5.2 |
| 尾线 Y 坐标（从低到高） | 10 AUX、18 CASIO、26 TI、34 USB Mini-B |

USB-C 开口为 14.4 × 8.0，USB-A 开口为 20.5 × 12.0，均包含紧凑线缆外模的进入余量。USB-C 内凹；新版短体 USB-A 为保持信号焊盘不动，前口相对壳前表面向外伸出约 1.925。开口保留插头外模余量。仍须用计划使用的 A-C、C-C 和 USB-A 线缆测试实际插合深度。

USB-C 的 [实际口部／胶壳量规校核](validation/upstream-usb-c-access.json) 从原生模型读得金属口 X−0.8299925，相对壳外壁 X−3 凹入 **2.170007**；座轴为 Y21.000043 / Z3.256191。壳体实体开口净宽高 **14.4×8.0、R1.5**。保守通过条件是胶壳前端至少 **2.2 mm** 长度内被 **13.0×6.0 mm 尖角矩形**包住，按座轴插入；Y/Z 各 ±0.25 的九种偏心位置均通过，最小模型壁距 0.18367。该矩形是允许的胶壳量规，不是 C430908 的已知外形。C430908 原厂图只给 Type-C 金属外露 **7.0±0.3**，没有胶壳宽／厚，不能据此保证所选实物已能插到底。首件须量胶壳前段、确认完全插合和锁持及电气连接；无需为未知尺寸改变冻结开口。

SW1 上方 `(X11…29, Y25.5…36.3)` 保留给导轨、拨叉和滑槽。导轨最低点 Z10.0，PCB 顶面实测 Z1.606203；此局部保留区不能按全板 8.6 高度通用放件。已单独检查实际导轨附近元件。拨叉侧槽按 ALPS 官方尺寸给拨杆名义单侧 0.20 mm、上下 0.25 mm 间隙。滑钮通过导轨承受手指的上下作用力，拨叉传递横向换挡运动。

R1.2 指拨件顶部为 7.0×6.0，M2 通孔为 3.1×2.3 的 X 向圆端槽，头窝为 5.0×4.2。头窝连续侧壁最薄 0.9、端壁 1.0；承压面 Z15.5，连续底厚 0.8。导向柱改为 4.6×2.7；Z12.2…14.7 的中央 X3.0 开窗沿 Y 打通，留下两个 0.8×2.7 端柱，消除低于喷嘴宽度的侧薄筋。顶盖槽仅沿 X 从 10.4 延长到 11.2，保留完整 6 mm 行程；外壳外包络、刻度和原 1.9 拨叉槽不变。端柱对叉件平台的最小夹紧接触面积由真实实体报告记录，长期抗滑移仍须首件验证。

同一颗 M2×6 与同一铜螺母允许拨叉相对指拨件在 X 方向 ±0.35 内装配校准，拧紧后成为固定连接。外壳外包络、内部支承导轨和四挡刻度保持不变；只有顶盖导向开口加长。库模型的默认内挡拨杆与名义位置相差约 −0.25；这是模型拟合值，不是原厂保证的实物尺寸。不能据此直接把所有实物拨叉固定偏移。装配时用实际中间挡定位，再锁紧。

## 材料、紧固件和打印

| 件 | 数量 | 建议规格 |
|---|---:|---|
| 上、下外壳 | 各 1 | PETG 或 ASA，0.4 喷嘴，0.2 层高，至少 4 道外墙，35% 填充，5 层顶底 |
| 上、下线夹及护套 | 各 1 | TPU 95A，100% 填充，分型面朝打印床 |
| 拨叉、指拨件 | 各 1 | PETG 或 ASA；拨叉直立加 brim，指拨外表面朝床 |
| 外壳螺钉 | 4 | M2 × 16，长度按头下计算；头径不超过 4.0，头高不超过 1.8 |
| 滑钮螺钉 | 1 | M2 × 6，相同头部限制 |
| 线夹外护套固定圈 | 4 | 2:1 热缩管，收缩前内径 8.0，切长约 8.0，分别包住四根 TPU 护套的 X86…94 区段 |
| 热熔铜螺母 | 5 | M2，名义外径 3.2，长度 2.5；四个装底壳、一个装拨叉 |

螺母孔默认 Ø3.0。随附试片提供 Ø2.9 / Ø3.0 / Ø3.1 三种孔和 1.9 × 2.0 的 SW 拨杆槽；同一试片可另用 TPU 打印来检查 Ø2.8 / Ø3.6 线孔。请先根据真实铜螺母、材料和打印机确定孔径及热熔温度。插入后不应把支柱顶面顶鼓。底壳孔深 2.5；螺钉尖端额外盲孔到 Z−3.8，距离外底面仍有 0.7。

顶盖以外表面朝下打印。导轨支撑台阶有短悬伸，按切片预览需要添加局部支撑，打印后清除并修平导向面；不要在整个顶盖腔内填满不可拆支撑。下壳以外底面朝下打印。外墙名义 2.0，结合舌厚 0.9，承接槽最薄外墙 0.85。

Mini-B、TI、Casio 三路线材统一采用 Ckmtw S002020047 / LCSC C430897 的 Ø3.8 外被，夹孔均为 Ø3.6，名义直径压缩量 0.20。原厂图为 1.5 m UL2725 #28 屏蔽数据线；保留 Mini-B 端约 250–300 mm，余线裁两段用于 TI/Casio。这里的 250–300 mm 是保留或裁切线段长度，须扣除 17.3 mm 夹持/护套段及内部走线，不能直接当成成品外露长度。未使用的芯线和屏蔽层按电气线束文件处理。

AUX 使用 26 AWG PH 三芯线束，采购线长 200 mm；在夹持段加连续外护套或热缩套管，使实测外径达到 Ø2.9–3.1，配合保留的 Ø2.8 孔，名义直径压缩范围为 0.10–0.30。不可把没有共同外被的裸露单根绝缘线直接压在线夹里。包套后的实测外径不在该范围时，应调整套管或该路 JSON 孔径，不能扩大整个线夹或缩放模型。

| 路径 | 线缆夹持外径 | TPU 夹孔 | 护套根部 / 末端外径 |
|---|---:|---:|---:|
| Mini-B、TI、Casio | Ø3.8 | Ø3.6 | Ø7.0 / Ø5.2 |
| AUX | Ø2.9–3.1，目标 Ø3.0 | Ø2.8 | Ø6.2 / Ø4.4 |

每条尾线保留 12 mm 渐缩 TPU 护套和一段 8 mm 热缩固定圈；四个固定圈均为装配 BOM 必要项，防止分体护套在弯线时张开。三根 Ø3.8 线的护套根部之间最小间隙为 1.0；按参考热缩壁厚 0.3 计算，X86 处固定圈之间仍有 0.625 间隙。线孔处名义上下颈壁 1.30，护套末端壁厚 0.80。以上是 CAD 尺寸，不是已验证的拉脱指标，必须测量样线、打印试片并做拉脱/弯折检查。

2.5 mm 公头候选 SP-2533A 标注出线孔 Ø4±0.5：标称对 Ø3.8 线有 0.2 直径间隙，但最小孔 Ø3.5 不能通过该线。因此需要样件量规确认实际出线孔 ≥Ø3.8，再按电气文件决定采购型号；不能据标称 Ø4 宣称全公差兼容。

## 装配

1. 打印试片，确认铜螺母孔、拨杆槽和实际线径配合；AUX 先包套到实测 Ø2.9–3.1，再检查夹孔。需要调整时改 JSON / 源参数并重建，不缩放整件。
2. 在下壳四个支柱中装入铜螺母，顶面与 Z0 支承面齐平。在拨叉上端装入第五个铜螺母，顶面与拨叉平台齐平。
3. 顶盖翻转，将拨叉从导轨开放端沿 X 推入。指拨件从外侧穿入滑槽，对准拨叉，装 M2 × 6。暂不锁紧滑钮螺钉，让拨叉可在短槽内左右校准。检查 6 mm 行程顺畅，指拨件与壳顶不摩擦。此时不要装 PCB。
4. 去除 PCB 安装孔毛刺；焊接后检查铜螺母和安装孔周围没有露铜、焊珠或元件侵入 R3.0 区域。将板平放在四个支柱上。
5. 先从四条尾线的 PCB 松散端各套入一段热缩管。按线序合拢 TPU 线夹，在外部渐缩护套的 X86…94 区段收缩四个固定圈，再将整套线夹放入下壳。热缩工序在壳体外完成，避免烘软刚性壳；不得烫伤线缆外被。随后按电气线束表焊接并检查 Mini-B、TI、Casio、AUX。外被必须延伸进线夹；剥皮后的芯线不得承担外部拉力。两种 2.5 mm 插头必须单独标识，不能只靠外形识别协议。
6. 检查两片线夹及四段热缩固定圈均已就位。内外挡肩分别位于壳壁内外；检查没有绝缘皮、屏蔽丝或细线被夹在壳体结合面。
7. 把实际 SW1 放到一个中间挡（标签 1 或 2），将指拨中心对准对应刻度。下降顶盖，让拨叉自然套住朝 −Y 的侧拨杆；拨叉在 ±0.35 校准范围内跟随实物，不横推开关。保持指拨中心对齐后，从顶部轻拧紧 M2×6。若需要超过该范围才能套合，停止并检查开关焊接和模型基准。确认舌槽自然就位。
8. 对角逐步拧紧四个 M2 × 16 螺钉，以壳体缝合拢为准；不靠螺钉把翘曲壳体拉平。不要对热熔螺母施加未经验证的扭矩值。
9. 在断开上游电源时测试四个挡位，再执行电气文档的上电测试。安装后确认每挡与外壳 0 / 1 / 2 / 3 标签一致。

四挡机械标签的预期对应为 0=原生 Mini-B、1=USB-A、2=TI、3=UART。实际电气开关接点和装配方向必须共同验证，标签本身不能证明连接正确。Casio / AUX 在 UART 路径中的具体选择与支持范围，以电气及线束文档为准。

拆下四个外壳螺钉即可接近 EEPROM、测试点及线束端接。只有更换线缆或重新打开 TPU 两半时才需要切除并更换外部热缩固定圈。开盖时先从侧拨杆垂直退出拨叉，不要向侧面撬动开关。

## 数字校验与首件检验

[R1.2实体差集记录](validation/adjustable_selector_revision.json) 确认本次改变顶盖导向开口和滑钮；底壳、两片TPU、拨叉、试片及参考板几何保持R1.1不变。

[线径修订记录](validation/cable_diameter_revision.json) 保存 R1.1 三路线径变更及与 R1 的实体差集比较；刚性壳体、滑钮、板体和所有接口坐标保持相同几何。

[validation_report.json](output/validation_report.json) 由脚本直接从 CAD 和输出 STL 计算，包含：

- 所有七个可打印件的 B-rep 合法性、独立实体数量、体积和边界；
- 每个 STEP 再导入后的体积差；
- 焊接 STL 重复顶点后每条边恰好关联两片三角形的闭合流形检查；
- 上下壳、PCB、TPU 线夹及插座保留包络之间的交叠体积；
- 两个滑钮件在四个挡位分别对壳体、PCB、开关壳和拨杆的干涉检查；
- 支承面、PCB 上下空间、舌槽以及螺钉尖端的名义余量；
- 从最终 TPU B-rep 圆柱面读取四路线孔直径，并核对护套及热缩固定圈之间的间隙。

原生工程中有 97 个 component，但 J3/J4/J5/J8 为直接焊线焊盘，不安装其库连接器模型。实际装配是 93 个器件（87 SMT、6 手工插件，含 SW1）。验证器保留原生 97 模型的记录，另列这四个 DNP 参考模型，实际配合结论按 93 器件给出。

实际原生板体 [BREP 校核](validation/native-fixed-board-brep.json) 已确认板厚 1.606203、四孔及 XY 方向。[可调滑钮校核脚本](validation/validate_selector.py) 用真实模型外拨杆逐挡移动，分别检查名义 0 与库拟合 −0.25；它还在 ±0.35 端点核算最大螺钉头、承压面和夹紧接触。[r7 全模型配合报告](validation/native-r7-pcba-fit.json) 已完成：93 个实装器件对现有壳体和紧固件零交叠，原生 97 个来源模型齐全。这是保留的 r7 历史诊断：当时 J2 的 STEP 钻孔被导出为源封装尺寸的十分之一，且塑胶安装面低 0.10。[逐实体诊断](validation/native-r7-j2-board-model-diagnostic.json) 将两者分开。现有最终原生板体与 CAM 已确认正确孔径和槽方向，批准的模型 Z+0.10 绑定已由最终原生源等价对照核实；完整规范装配采用已通过的源设计总装。旧版含立式 J2 的失败诊断已经被标为 superseded，不代表当前壳体结论。 经批准的 J2 模型 Z+0.10 灵敏度校核保持零壳体干涉：到底壳最小 1.7062、到顶盖 3.1938；前口悬伸不变。该显式分析不冒充新的原生导出。

首件仍须检查打印收缩、铜螺母扭矩、所有插头的完整插合、每条线的拉脱及反复弯曲、开关四挡位置和 EEPROM / 测试点可达性。拉力目标和寿命要求应由项目确定；没有完成测试前，不声明任何拉脱力、阻燃、密封、防水或 USB 合规等级。

## 重建

可复现命令以 Linux 参考环境为准：Python 3.12、CadQuery 2.7、Blender 4.3、FreeCAD 1.0，并安装 DejaVu Sans 字体（常见发行版的软件包为 `fonts-dejavu-core`）。`blender` 与 `freecadcmd` 应位于 PATH；字体应能由 OpenCascade 以 `DejaVu Sans` 查到，且 ReportLab/Pillow 可读 `/usr/share/fonts/truetype/dejavu/`。这是明确的运行时依赖，不是工程工作目录。Windows 可直接打开交付的 STEP/FCStd/STL；运行生成脚本时可使用相同 Linux 环境，例如 WSL。

在新检出的仓库根目录建立独立 Python 环境后安装 `mechanical/requirements.txt`，再进入 `mechanical` 运行下列命令。所有 CAD 输入、原生 r7 模型和源孔合同均用仓库内相对路径引用；不需要旧 `tmp/`、本机 D 盘工程或任何聊天工作目录。工程的哈希验证要求检出字节保持原样，不应让 Git 自动改写 STEP/JSON 的行尾；仓库根级 `.gitattributes` 已禁用文本规范化。[干净副本输入审查](validation/release-portability.json) 已确认所需输入齐全、不被忽略、无旧工作目录依赖。

依赖：CadQuery 2.7.0、NumPy、Pillow、ReportLab、pypdf、PyMuPDF；图片使用本机 Blender 4.3 的 CPU Cycles 渲染，不使用图像生成服务。[requirements.txt](requirements.txt) 列出 Python 依赖；FreeCAD 1.0 用于输出原生工程。

```bash
python generate_mechanical.py
QT_QPA_PLATFORM=offscreen freecadcmd export_freecad.py
python make_release.py
```

仅快速检查修改的几何时可使用 `CALXUS_SKIP_RENDER=1 python generate_mechanical.py`。该开关要求此前已完成过完整重建，保留两张交付图及 `tmp/` 中的 PDF 内部插图；不能用这一步代替最终完整重建与 PDF 视觉检查。

[blender_render.py](blender_render.py) 仅渲染 CAD 三角网格。精简目录保留 [机械参考装配预览](output/calxus_assembled.png)、[机械参考爆炸预览](output/calxus_exploded.png) 及上述两张源设计真实器件预览，临时场景与 PDF 内部插图由脚本重建到 `tmp/`。不提交 Blender 场景或重复 ZIP。组装图中的插座外观代理用于表达朝向，不是厂商机械图。

实际来源复核可直接运行：

```bash
python validation/validate_pcba.py validation/Calxus_RevA_r7_PCBA.step.gz validation/native-r7-pcba-fit.json --slider-offset -1 --fork-calibration -0.25
python validation/validate_selector.py validation/Calxus_RevA_r7_PCBA.step.gz validation/native-r7-selector-motion.json
python validation/validate_j2_source_mount.py validation/Calxus_RevA_r7_PCBA.step.gz ../validation/native-r7-j2-drill-expectations.json validation/native-r7-j2-source-drill-counterfactual.json
```

源设计总装使用新检出仓库中已交付并冻结的七件 STEP/STL，不重新改变打印几何。上面的机械重建流程与下面的冻结整机重建流程是两个独立入口；不要先覆盖冻结文件后再期待其旧字节哈希仍一致。若要研究机械参数修改，请在独立工作副本运行机械生成器；整机来源核验从保留原始冻结文件的干净副本开始。将候选工程、三份源孔合同和 r7 原生模型放在本仓库原有相对路径后运行：

```bash
python assemble_source_pcba.py
python validation/validate_source_assembly.py
```

生成器核对 97 个原生模型绑定、唯一的 J2 高度变换、最终候选 SHA 与全部孔合同 SHA；独立回读器重新打开整机 STEP，验证 114 个对象的实体合法性、包围盒和体积，并直接读取 247 个孔的圆柱面和底面内环。孔中心采用保存源 `centerX/Y` 的名义坐标；通用 `padOffset` 语义不在本报告中作保证，源合同给出的最大径向不确定性约 0.000235，仍需最终 CAM 对照。此数值不通过扩大真实封装或孔径来补偿。

第一项明确区分 `static_enclosure_fit_pass`（壳体配合）与 `static_fit_pass`（含原生连接器/板体配合），在保留的 r7 诊断输入上，后者受当时 J2 导出孔/模型安装面异常阻挡。第三项只对内存副本按原生封装源孔尺寸作诊断，不修改源 STEP、不代替 CAM，也不输出冒充原生的修复模型。

最终原生输入及加工证据可独立复查，以下命令不重建 CAD 或渲染图片：

```bash
python validation/compare_native_final_mechanics.py
python validation/validate_final_board_representation.py
python validation/finalize_mechanical_acceptance.py
```

这些步骤读取仓库内的最终原生工程、保留的实际板体 STEP、原生孔合同、Gerber ZIP 及其独立检查记录。结果明确保留原生 STEP 省略 VIA 的限制，不用显示模型替换实际加工孔表。

[make_release.py](make_release.py) 只优化 PDF 内嵌图片并刷新 [SHA-256 清单](output/artifact_manifest.json)，不会修改 CAD 几何或另建 ZIP；PDF 的文字、字体、尺寸线和其他矢量内容保持不变。

## 依据

- ALPS 官方 [SSSS224100 产品页及尺寸图](https://tech.alpsalpine.com/e/products/detail/SSSS224100/)：15 × 3.5 × 3.5 本体、1.5 拨杆宽、2 侧向伸出、2.5 拨杆中心高度、2 挡距。
- HRO 官方 [TYPE-C-31-M-12](https://en.krhro.com/Product-Details/726.html)：8.94 × 7.35 × 3.16 名义本体。
- 本项目 [EDA 器件库证据](../hardware/evidence/eda_parts_catalog_full.json) 与 [机械接口 JSON](mechanical_contract.json)：实际选中封装和锁定放置坐标。
- SHOU HAN [AF 10.0 HC6.3 / C456017 原厂图](https://datasheet.lcsc.com/datasheet/pdf/d8f5df2b196cdbe2164d9785cc185649.pdf?productCode=C456017)：本体 13.2×10.0×6.3，卧式双盾脚。原 C718032 经实际 PCBA STEP 及原厂图确认是 H15 立式座，因与顶盖相交已淘汰，不能继续使用旧商品图的外观判断。

- Ckmtw [S002020047 / C430897 原厂图](https://datasheet.lcsc.com/datasheet/pdf/4be3348a50351aa811fbe41e427c005c.pdf?productCode=C430897)：A 版，2012-11-01；UL2725 #28×1PR + #28×2C + AL + 64 编织，Ø3.8 黑色外被。原图 PDF 的 SHA256 记录于机械合同。
