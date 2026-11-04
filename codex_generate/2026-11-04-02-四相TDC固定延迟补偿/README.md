# 四相TDC固定延迟补偿实验归档

**实验验收：FAIL。** 本分支只归档既有实验，不重新修改RTL或计算数据。20 MHz完整暂定帧漏沿/错配和500 MHz setup失败证据完整保留。

- [外部技术审查说明](review_package/README_FOR_REVIEW.md)
- [全部文件清单](FILE_LIST.md)
- [原始来源→审查包映射](review_package/FILE_INDEX.csv)
- [本地审查包→Git文件映射](PUBLICATION_INDEX.csv)
- [原始最终RMSE报告](review_package/08_Reports/original/FINAL_RMS_COMPARISON.md)
- [归档完整性验证](review_package/ARCHIVE_VERIFICATION.json)

补偿前后各五份完整RTL、全部原CSV与失败日志、两套BIT/DCP/SDF/实现后网表和时序报告均在review_package。>5 MB原日志在Git使用无损gzip；解压SHA必须与PUBLICATION_INDEX的original_sha256相同，未裁剪告警。实现文件与.gz由Git LFS保存，克隆后执行`git lfs pull`。SHA256SUMS校验Git实际文件；review_package内的原SHA清单针对解压后的本地审查包。

既有RMSE（ps）：25.3 ns 135.602→53.147；20 MHz/50% 143.269→69.735；10 MHz**完整暂定帧**125.406→66.700。10 MHz/50%是独立项目，不能混同。

两个本地ZIP位于原工作空间任务目录：`D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate/2026-11-04-02-四相TDC固定延迟补偿/`，名称为TDC_Review_Source_Results.zip和TDC_Review_Implementation.zip；ZIP_MANIFEST.json记录大小与SHA。ZIP没有重复提交到Git；其全部关键内容以本目录逐文件形式上传。工具缓存不归档，清单见review_package/EXCLUDED_CACHE_FILES.csv；原工程和历史任务未覆盖。
