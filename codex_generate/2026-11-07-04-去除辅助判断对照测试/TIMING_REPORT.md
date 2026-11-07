# 尚未进行NoAux实现与时序验证

| 阶段 | 状态 |
|---|---|
| 综合、布局布线 | NOT_RUN |
| 核心Setup/Hold | NOT_EVALUATED，WNS/TNS/WHS/THS均N/A |
| XSim MAX-SDF | NOT_RUN |
| NoAux BIT/LTX | NOT_GENERATED |

原因：完整RTL矩阵中补充短低间隔测试两版均有3次冲突/错配，整体RTL门保持FAIL，等待验收范围明确。预备构建脚本严格检查RTL门，尚未执行。不能以Corrected已有STA/SDF代替NoAux结果。
