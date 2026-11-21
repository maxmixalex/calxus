# 实际 STEP 板厚差异定位

从原生导出的 `Calxus_PCBA_corrected.step.gz` 已接收部分数据中，完整提取了 Board BREP。板框 XY 方向正确，4 个安装孔中心与机械合同差值小于 0.0002 mm；板体却为 Z=0..2.905898439303 mm。独立导入得到 1 个有效实体。该压缩文件尚未完整传输，因此不能宣称整包 CRC 已校验。

当前 `getStackup()` 证据记录的总厚度为 1.6062553861084914 mm。只读磁盘 `D:/Works/Calc/Calxus/pcb/PCB1.epcb2` 得到的是旧快照：目标 PCB UUID 的原有 9 条 LAYER_PHYS 总和为 62.994 mil，361 仍是 59.449 mil 的 FR4；没有新增的 15、16、362、363 条记录。该磁盘快照不能替代当前 live document source。当前 Calxus session 为 origin=user、path=null，未建立双向工程目录绑定；PCB1.epcb2 只是早前导出文件，旧参数不代表 save() 失败。

**差异可精确重建：**

`(62.994 + 51.411221555362445) × 0.025400050800101596 = 2.905898439303084 mm`

其中第二项恰好是当前新增的内铜 15/16、芯板 362、下半固化片 363 四条厚度之和。该结果与 STEP 实体厚度相差 8.4e-14 mm。导出器保留了原有层的旧厚度，同时计入新添加的物理层。旧 361 被新 PP7628 替换后的厚度变化没有体现在这个 STEP 中。未找到足以证明“另有隐藏 1.3 mm 介质层”的证据。

U4 的真实 STEP 装配变换 #13346 使用 Z=2.905898439303 mm，说明元件也被放在错误板顶，不只是板体显示偏厚。

## 建议的可验证修复流程

1. 当主任务回到 PCB 页面时，将当前 `getDocumentSource()` 导出到一个新文件，只按目标 UUID 核对每个 LAYER_PHYS 的唯一性、最新厚度、ticket 和关联 LAYER。
2. 如果源记录正确，保存并重新加载 PCB/工程，使 3D 导出状态重建；不删除正确的新芯板或 PP7628 层，不按错误厚度修改外壳。
3. 先重新导出板体或读取导出 STEP 的 Board BREP。确认实体厚度约 1.6063 mm，四孔和板框仍然正确，再传输完整 PCBA。
4. 如果重新加载后仍保留旧厚度，应通过原生层叠设置界面重新应用同一组物理参数，再用实体厚度复核；不要仅依赖 `getStackup()` 总和。

官方静态 API 文档确认 `getStackup()` 只读；`modifyLayer()` 的 property 仅有 name、type、color、transparency，不支持 thickness/material。它不能作为物理层厚度的修复接口。

本轮仅进行文件和文档读取，没有切换 EDA 活动页、修改工程源或改动冻结外壳。来源与数值保存在 [JSON 诊断](stackup_step_diagnosis.json)、[磁盘元数据](pcb1_disk_stackup_metadata.json)、[官方 API 文档快照](layer_api_docs.json)。
