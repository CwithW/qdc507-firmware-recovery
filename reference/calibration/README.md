# 原始校准分区参考副本

**REFERENCE ONLY / UNTESTED / DO NOT FLASH. use at your risk.**

这里保留一台 QDC507 设备的 EFS2、sys_rev 原始分区镜像形式，已对识别出的
IMEI、设备序列号、IMSI、ICCID 置无效值。不是完整匿名化镜像，也不是可刷入的校准包。
仅供离线格式和校准数据研究，不提供刷入、恢复、导入或写入命令。

## 内容与来源

| 文件 | 长度 | 修改字节数 |
|---|---:|---:|
| EFS2.redacted.bin | 17,825,792 | 2,296 |
| sys_rev.redacted.bin | 3,407,872 | 90 |

这两份参考源自 `QDC507GLEFM21_01.001.01.009` 设备备份，
与仓库主恢复固件的 `01.001.02.004` 版本不同。不得据此假定跨版本或跨设备兼容。
保持原分区长度和字节偏移；仅含 NAND 页正文，不含 OOB。
未附 usr_data、QCN/XQCN、整片 NAND、原始设备标识、原始镜像哈希或私有日志。

## 脱敏范围

对已解析文件的身份内容，以及原始分区中匹配的副本，使用等长 `0x00` 字节替换。
零值是无效占位，不能作为可用设备身份。原本为空或填充的记录可能仍为 FF / F。

- IMEI：`nvm/num/550`、`nv/item_files/quectel/quec_imei_backup`。
- 设备序列号及候选记录：`nvm/num/7233`、`nv/item_files/quectel/aaa_bbb`。
- IMSI：`nvm/num/923`。
- ICCID：`nv/item_files/mcfg/mcfg_last_autoselect_iccid`、`nv/item_files/modem/uim/mmgsdi/rpm_iccid`。
- 对已识别值检查 ASCII、UTF-16 LE/BE、常见 BCD/nibble 顺序及填充形式；
  同时清除原始镜像中可见的 14–22 位连续数字候选记录。

匹配会覆盖能识别出的历史副本，但不保证识别所有历史身份、编码、压缩或加密内容。
本次未声称删除所有凭据、运行状态、其他未知设备标识或全部个人信息。
RF 校准数值本身来自这台设备，仍然具有个体差异，不能代替另一台设备自己的校准。

## 验证与限制

两个修改后镜像均可重新离线解析，列出的身份记录被解析为无效值，已知敏感模式未再命中。
每个镜像的 943 个 `nv/item_files/rfnv/*` 文件与原备份逐字节一致。
这只验证该 RFNV 子集，不代表全部校准项均已识别。
逐文件 SHA-256、修改计数及验证结果见 [sanitization.json](sanitization.json)。

未重算或承诺修复内部校验、备份摘要、文件系统事务/日志关系；未验证设备是否接受这些修改。
离线可解析不代表能安全刷写、正常启动或联网。**请勿刷入设备。**

两个文件只位于 reference/calibration，不在 firmware/manifest.json、rawprogram XML 或刷写白名单中。
默认更新和 NAND 重建模式都继续拒绝擦写 EFS2/sys_rev，其他四个保护区也保持不擦写。

解析器：[Crawlerop/dumpefs2](https://github.com/Crawlerop/dumpefs2/tree/86d2c9970894ec6ede2e72b6c126a3e2ac640d75)。
NV 字段参考：[openpst/libopenpst dm_nv.h](https://github.com/openpst/libopenpst/blob/master/include/qualcomm/dm_nv.h)。
使用上述解析器和本地 Python 检查，未操作实机。
