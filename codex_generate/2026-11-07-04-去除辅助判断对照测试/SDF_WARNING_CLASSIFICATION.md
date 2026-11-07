# NoAux MAX-SDF告警分类

官方XSim 2022.2，slow/MAX，严格全局注释成功、零未匹配诊断。ANNOTATION.json记录请求的CELL/IOPATH/互连/时序检查项计数，不把它称为逐项成功率。未关闭specify、timing check或互连延迟。

完整运行保留1073744条MMCM CLKOUT5/6零周期模型告警。生成网表中两路明确连接UNCONNECTED导线；原时钟向导配置未改，对应告警单独计数，不当作使用中500MHz/100MHz时钟的真实周期违例。

保留1条启动异步复位首级recrem告警。仅明确命名rst_sync_*_reg[0]、发生于有效粗计数epoch之前的启动告警分类为此类；第二级、下游或运行期间同类告警不自动放行。

保留85541条异步TDL thermometer首级采样告警，这些节点直接采集异步PWM，不按普通同步数据路径处理；此分类不证明实际硬件亚稳态概率。NoAux辅助判断已旁路，原异步pwm_meta首级未出现运行告警。

保留110条非反馈ILA时序告警，与STA中历史14个ILA2负端点分别记录，不能把两种计数混为一谈。ILA输出不反馈TDC测量/FIFO通路。

除这些明确分类外，任何核心同步或无法分类的WARNING/ERROR均阻断验收；本次为0。功能冲突100、连续同极性诊断103及Merge错误2属于独立事件统计，不因时序告警分类而忽略，具体归属见SDF_ERROR_ATTRIBUTION.md。
