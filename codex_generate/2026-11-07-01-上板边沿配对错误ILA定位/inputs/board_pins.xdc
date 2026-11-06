# PWM板级输入使用AD23，电气标准保持原来的1.8V LVCMOS。
# 在原TDL布局及工程约束之后读取本文件，避免旧的AF20绑定覆盖新引脚。
set_property PACKAGE_PIN AD23 [get_ports pwm_in]
set_property IOSTANDARD LVCMOS18 [get_ports pwm_in]
