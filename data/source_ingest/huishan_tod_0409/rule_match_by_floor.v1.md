# 惠山TOD逐层规则匹配摘要

本文件用于把惠山TOD测试案例按楼层对接统一规则库，保证“各层全覆盖、无缺项”。

规则来源边界：

- `C2工具`
- `2024天街建标`

说明：

- 惠山TOD仅作为测试案例
- 不进入基础规则库来源
- 状态包括 `matched`、`partially_matched`、`needs_measurement`、`needs_refined_detection`、`not_primary`、`not_applicable`

## 页序覆盖

- `0` 封面
- `1` 总平面图
- `2` B2F平面图
- `3` B1F平面图
- `4` 1F平面图
- `5` 2F平面图
- `6` 3F平面图
- `7` 4F平面图
- `8` 5F平面图
- `9` 6F平面图
- `10` 6F夹层平面图

## 逐层匹配

### 0 封面

- 作用：样本识别页，不参与空间诊断
- 主要状态：`LF-C2-VALUE-LOGIC-0001` 为 `not_primary`

### 1 总平面图

- 重点：高价值城市界面、TOD到达、滨水资源、入口前场
- 已匹配：
  - `LF-C2-HIGH-VALUE-FRONTAGE-0001`
  - `LF-C2-TOD-INTEGRATION-0001`
  - `LF-C2-ARRIVAL-EXPERIENCE-0001`
- 需量化：
  - `LF-STD-OUTDOOR-PLAZA-0001`
- 部分匹配：
  - `LF-C2-SCENE-PLAZA-0001`
  - `LF-C2-SCENE-IN-SKELETON-0001`
  - `LF-C2-STOREFRONT-FORECOURT-0001`
- 需精细识别：
  - `LF-C2-FACADE-ENTRY-0001`

### 2 B2F平面图

- 重点：停车规模、地下支撑逻辑、TOD项目地下成本控制
- 已匹配：
  - `LF-C2-PARKING-EFFICIENCY-0001`
- 部分匹配：
  - `LF-C2-UG-COMMERCIAL-0001`
  - `LF-C2-VALUE-LOGIC-0001`
- 不适用：
  - `LF-STD-RESTROOM-0001`

### 3 B1F平面图

- 重点：交通客流转化、B1经营定位、西侧主力牵引、东端节点承流
- 已匹配：
  - `LF-C2-B1-METRO-0001`
  - `LF-C2-UG-COMMERCIAL-0001`
  - `LF-C2-TOD-INTEGRATION-0001`
- 部分匹配：
  - `LF-C2-MAIN-ANCHOR-0001`
  - `LF-C2-SUNKEN-CONVERSION-0001`
- 需精细识别：
  - `LF-C2-SUPERMARKET-0001`

### 4 1F平面图

- 重点：首层一字型主骨架、西侧主力锚点、东端高价值界面转化、入口体系
- 已匹配：
  - `LF-C2-HIGH-VALUE-FRONTAGE-0001`
  - `LF-C2-MAIN-ANCHOR-0001`
  - `LF-C2-DISTRIBUTION-NODES-0001`
- 部分匹配：
  - `LF-C2-FACADE-ENTRY-0001`
- 需量化：
  - `LF-STD-CIRCULATION-0001`
  - `LF-STD-WALKWAY-0001`
- 需精细识别：
  - `LF-STD-ENTRY-0001`

### 5 2F平面图

- 重点：中庭与节点节奏、扶梯组团、走道尺度、二层体验层质量
- 已匹配：
  - `LF-C2-DISTRIBUTION-NODES-0001`
  - `LF-STD-ATRIUM-0001`
  - `LF-STD-ESCALATOR-0001`
- 部分匹配：
  - `LF-C2-INTERIOR-CONSISTENCY-0001`
- 需量化：
  - `LF-STD-WALKWAY-0001`
  - `LF-STD-CIRCULATION-0001`

### 6 3F平面图

- 重点：高层东端复合节点、端头价值释放、异形边界效率
- 已匹配：
  - `LF-C2-LOW-EFFICIENCY-END-0001`
- 部分匹配：
  - `LF-C2-DISTRIBUTION-NODES-0001`
- 需量化：
  - `LF-STD-CIRCULATION-0001`
- 非主判断：
  - `LF-C2-SCENE-PLAZA-0001`

### 7 4F平面图

- 重点：支路过深风险、端头消极空间、高层店铺效率
- 已匹配：
  - `LF-C2-LOW-EFFICIENCY-END-0001`
- 部分匹配：
  - `LF-C2-DISTRIBUTION-NODES-0001`
- 需量化：
  - `LF-STD-WALKWAY-0001`
  - `LF-STD-CIRCULATION-0001`

### 8 5F平面图

- 重点：高层骨架延续性、东端复杂区持续性、高层吸附力
- 部分匹配：
  - `LF-C2-LOW-EFFICIENCY-END-0001`
  - `LF-C2-DISTRIBUTION-NODES-0001`
- 需量化：
  - `LF-STD-CIRCULATION-0001`
- 需精细识别：
  - `LF-STD-RESTROOM-0001`

### 9 6F平面图

- 重点：复合功能层判断、大空间运营逻辑、高层独立功能区
- 已匹配：
  - `LF-C2-VALUE-LOGIC-0001`
- 部分匹配：
  - `LF-C2-INTERIOR-CONSISTENCY-0001`
- 非主判断：
  - `LF-STD-CIRCULATION-0001`
  - `LF-C2-LOW-EFFICIENCY-END-0001`

### 10 6F夹层平面图

- 重点：夹层空间叠加关系、高层复合运营模式、高层功能组织
- 已匹配：
  - `LF-C2-VALUE-LOGIC-0001`
- 部分匹配：
  - `LF-C2-INTERIOR-CONSISTENCY-0001`
- 非主判断：
  - `LF-STD-ATRIUM-0001`
  - `LF-STD-WALKWAY-0001`

## 跨层高优先级规则

- `LF-STD-CIRCULATION-0001`
  - `1F-5F` 已识别骨架，仍需量化长度与进深
- `LF-STD-ENTRY-0001`
  - 总平与 `1F` 都指向东侧高价值到达面，入口数量和主次层级仍需精细识别
- `LF-C2-LOW-EFFICIENCY-END-0001`
  - `3F-5F` 东端复杂区构成连续高层风险带
- `LF-C2-TOD-INTEGRATION-0001`
  - 总平、`B1`、`1F` 构成TOD一体化判断主链路
- `LF-C2-VALUE-LOGIC-0001`
  - 总平、`B2`、`6F`、`6F夹层` 需要回到综合价值逻辑判断

## 当前仍未量化的问题

- `1F-5F` 主流线长度和平均进深
- `2F` 中庭净宽、面积及扶梯距离
- `1F-2F` 主次走道净宽
- 总平入口广场坡度和高差关系
- 高层卫生间服务半径和上下对应关系
