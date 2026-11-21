# Calxus electrical design inputs

These files describe RevA/r7 (CH444G, one selected calculator; J2 C456017 right-angle USB-A). The current schematic has 97 components and 345 logical pins. They are not a substitute for the final JLCEDA project, its ERC/DRC, actual fabrication files, or measured hardware qualification.

- `calxus_design_input.json`: 120 references:87 SMT,6 manual TH,4 pad-only connectors,23 PCB-only test pads; pins,nets,sheets,placement and sourcing IDs.
- `calxus_pin_net.csv`: per-pin connection table, including NC.
- `calxus_bom_draft.csv`: complete engineering BOM, including DNP pad templates.
- `bom_smt_reference.csv`:87 SMT pieces grouped into purchasing rows. Validate final exported EDA BOM/CPL before ordering.
- `manual_assembly_reference.csv`:6 through-hole parts, removable shunts, and manual harness materials; stock gaps are explicit.
- `harness_procurement_reference.csv` / `harness-procurement.json`: exact cable/plug/housing/terminal sourcing with observed inventory, MOQ, original-drawing facts, and remaining qualifications.
- `electrical-design.zh-CN.md`: architecture and critical electrical choices.
- `sources.json`: manufacturer references and retrieval hashes.
- `placement_check.py`: reads `../evidence/eda_parts_catalog_full.json`, checks actual-library envelopes, not copper DRC. Run from any directory with Python3.

`build_design_input.py` regenerates JSON and flat CSV snapshots after deliberate source edits. Final PCB placement may be refined in JLCEDA, so manufacturing position files must come from that final PCB.

USB高速预布线输入与跨层连通/差长验证见 `usb-routing.zh-CN.md`、`usb_route_plan.json`、`usb_route_validation.json`。路线输入不替代本地EDA最终DRC与制造导出。

`usb_route_input_r4.json` 等带历史修订号的路线输入保留原器件数据，只用于复核对应历史规划；其 J2 与引脚计数不能作为现行采购或制造依据。现行器件/引脚合同以 `calxus_design_input.json` 为准。

关键接地、QFN裸露焊盘VIPPO工艺及L4高速隔离区域见 `ground-and-vippo.zh-CN.md`。实际线材、公头与AUX压接件见 `harness-procurement.zh-CN.md`；2026-11-21 已核 C430897、C430908、C111514、C111515、C53413426 实时现货，两个2.5mm TRS公头首选 C4992833 及替代 C4992470 均为0库存，不能称整机零件全部现货。通用绝缘/护套耗材按指定装配尺寸采购，特殊 AUX 计算器端公头按机型另外核对。
