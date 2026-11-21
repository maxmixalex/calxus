# USB高速布线指令与验证

`usb_route_plan.json` 是基于本地JLCEDA真实焊盘坐标生成的布线输入。它不是成板信号完整性报告。

- 98条线段、12颗信号通孔、6颗相邻GND回流通孔，单位全部mil。
- API层号1=L1顶层，2=L4底层；内层15/16分别L2/L3连续GND。
- 每条track字段为net/layer/x1/y1/x2/y2/width；每颗via为net/x/y/diameter/holeDiameter/fromLayer/toLayer。过孔须创建为贯通L1至L4，不能仅按数值层号当成物理相邻层。
- 主干宽9.53125mil、边缘间距6mil。信号/回流孔0.20mm、焊盘0.50mm。
- 26个高速焊盘全部同网连通；连通校验包含铜面相交、通孔跨层、USB-C重复脚、USBLC6两侧同一通道焊盘。
- 按实际库矩形保守包络、异网线段、所有计划通孔、测试点、安装孔禁布区检查，6mil间距违规为0。原生EDA DRC仍是制造输出前必要检查。
- C14原生位置已移动至(38.5,13.1)mm；输入快照仍为13.0，校验使用此更靠近高速扇出的旧位置，因此该移动增大间距。

| PCB路径 | D+长度(mm) | D−长度(mm) | 绝对差(mm) |
|---|---:|---:|---:|
| UP_A_orientation | 20.53728 | 20.68962 | 0.15234 |
| UP_B_orientation | 17.58072 | 17.73306 | 0.15234 |
| NATIVE | 67.83919 | 67.83965 | 0.00046 |
| USB_A | 38.87422 | 38.64396 | 0.23026 |
| USB_C_A_to_NATIVE | 88.37646 | 88.52927 | 0.15280 |
| USB_C_A_to_USB_A | 59.41150 | 59.33358 | 0.07793 |
| USB_C_B_to_NATIVE | 85.41990 | 85.57271 | 0.15280 |
| USB_C_B_to_USB_A | 56.45494 | 56.37702 | 0.07793 |

长度按中心线加1.6mm通孔长度计算。每个支路含3.2mm孔柱，完整选通路径含6.4mm孔柱。未计连接器内部、CH444封装/硅片、外接线缆；铜箔宽度造成的拐角捷径及真实介质传播时延也未做场求解。所有分支及两种USB-C朝向的完整路径均≤0.254mm差长。

复核顺序：运行`plan_usb_routes.py`、`verify_usb_routes.py`、`render_usb_routes.py`；需要Python、numpy、shapely和matplotlib。截图是几何工程图，非本地EDA导出截图。

对照证据：`../evidence/pcb-components-pads-r4-actual.json`、`../evidence/eda_parts_catalog_full.json`。规划不应覆盖后续原生DRC修正，实际制造使用本地EDA完成布线后重新导出的Gerber/钻孔/CPL。
