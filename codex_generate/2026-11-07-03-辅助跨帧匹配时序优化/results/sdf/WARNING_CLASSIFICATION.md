# MAX-SDF 告警分类依据

最小测试的未分类告警为 671623 ps 的 `u_tdc_fine_layer/rst_sync_90_reg[0]` `$recrem`，早于有效粗计数 epoch 677150 ps 和第一输入边沿 5200000 ps。RTL 为带 ASYNC_REG 的两级异步置位/同步释放复位同步器；告警位于第一级异步 CLR 释放，未出现第二级或下游同步通路告警。112 个脉冲全部正确，控制输出无未知值。它单独归类为启动复位第一级恢复/撤销告警，保留原日志；不认定为运行期核心 Setup/Hold 违例。脚本只接受 epoch 前、明确命名的第一级 `$recrem`；其他复位告警仍阻断。初始未分类的 FAIL 摘要也保留。

网表的 MMCM CLKOUT5、CLKOUT6 明确接 `NLW_mmcm_adv_inst_CLKOUT5_UNCONNECTED` 和 `...CLKOUT6_UNCONNECTED`。对应零周期模型告警独立计数，不作为使用中时钟的真实周期违例。

TDL thermo_q 和辅助 pwm_meta 是异步输入的第一级采样器，Setup/Hold 告警独立计数；不能据此推断硬件亚稳态概率。ILA 非反馈告警独立保留。任何其余时序告警或非时序 WARNING/ERROR 仍使 MAX_SDF 门失败。未关闭任何 timing check。
