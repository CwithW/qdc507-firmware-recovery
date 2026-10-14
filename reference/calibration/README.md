# 原始校准与持久化分区参考副本

**REFERENCE ONLY / UNTESTED / DO NOT FLASH. use at your risk.**

这里保留一台 QDC507 设备的 EFS2、sys_rev、usr_data、sec、machine、misc
六个原始分区镜像形式，已对识别出的
IMEI、设备序列号、IMSI、ICCID 置无效值。不是完整匿名化镜像，也不是可刷入的校准包。
仅供离线格式和校准数据研究，不提供刷入、恢复、导入或写入命令。

## 内容与来源

| 文件 | 长度 | 修改字节数 |
|---|---:|---:|
| EFS2.redacted.bin | 17,825,792 | 2,296 |
| sys_rev.redacted.bin | 3,407,872 | 90 |
| usr_data.redacted.bin | 22,020,096 | 31,718 |
| sec.redacted.bin | 524,288 | 0（全 FF） |
| machine.redacted.bin | 655,360 | 0（全 FF） |
| misc.redacted.bin | 524,288 | 0（全 FF） |

这六份参考源自 `QDC507GLEFM21_01.001.01.009` 设备备份，
与仓库主恢复固件的 `01.001.02.004` 版本不同。不得据此假定跨版本或跨设备兼容。
保持原分区长度和节点位置；usr_data 中命中的压缩节点重新编码，文件内容仍为等长替换。
仅含 NAND 页正文，不含 OOB。
未附 QCN/XQCN、整片 NAND、原始设备标识、原始镜像哈希或私有日志。

## 脱敏范围

对已解析文件的身份内容，以及原始分区中匹配的副本，使用等长 `0x00` 字节替换。
usr_data 同时检查压缩内容；修改后的数据节点重新计算 CRC，节点长度和位置不变。
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

EFS2/sys_rev 两个修改后镜像均可重新离线解析，列出的身份记录被解析为无效值，已知敏感模式未再命中。
这两个镜像各自的 943 个 `nv/item_files/rfnv/*` 文件与原备份逐字节一致。
这只验证该 RFNV 子集，不代表全部校准项均已识别。
usr_data 扫描了全部 165 个可解析 UBIFS 数据节点（含压缩数据和能解析的历史节点），
共修改 17 个数据节点；重新解出全部 24 个普通文件，5 个文件存在预期的脱敏内容变化，
其余文件内容不变。扫描的已知标识模式及长数字候选记录未再命中。
sec、machine、misc 在该设备备份中逐字节全为 FF，原样保留，不代表其他设备也应为空。

usr_data 不是纯校准分区，仍包含设备持久化配置（包括网络相关配置）。
本次仅按上述范围脱敏，没有完整审计或删除其他配置、凭据或未知隐私字段。

逐文件 SHA-256、修改计数及验证结果见 [sanitization.json](sanitization.json)。

## 具体字段与修改偏移

完整明细见 [redaction-map.json](redaction-map.json)，不包含原值或原始字节。
所有原始偏移均以各分区镜像起点为 0，单位为字节；不是整片 NAND 地址。
`offset_hex` 与 `offset` 等价，区间为 `[offset, offset + length)`。

- `changed_ranges`：逐字节比较原始与参考镜像所得的全部实际修改区间，不遗漏 CRC 或重压缩字节。
- `identity_fields`：EFS2/sys_rev 的具体字段路径、记录长度及可定位的原始记录副本偏移。
- `decoded_files`：usr_data 中修改过的文件路径及解压后文件内修改区间。
- `modified_ubifs_nodes`：每个修改节点的原始偏移、长度、关联文件候选、解压内容区间，
  并分别标注 CRC 字段、压缩类型字段和编码载荷范围。无关联文件候选表示历史节点未匹配当前文件。
- 压缩内容的逻辑文件偏移不能直接作为原始镜像偏移使用；重压缩字节变化不等于身份字段长度。

| 分区 | 实际修改字节 | 连续修改区间数 |
|---|---:|---:|
| EFS2 | 2296 | 200 |
| sys_rev | 90 | 8 |
| usr_data | 31718 | 196 |
| sec | 0 | 0 |
| machine | 0 | 0 |
| misc | 0 | 0 |


除 usr_data 中修改节点的 CRC 外，未重算或承诺修复其他内部校验、备份摘要、文件系统事务/日志关系；
未验证设备是否接受这些修改。
离线可解析不代表能安全刷写、正常启动或联网。**请勿刷入设备。**

六个文件只位于 reference/calibration，不在 firmware/manifest.json、rawprogram XML 或刷写白名单中。
默认更新和 NAND 重建模式都继续拒绝擦写这六个保护区。

解析器：[Crawlerop/dumpefs2](https://github.com/Crawlerop/dumpefs2/tree/86d2c9970894ec6ede2e72b6c126a3e2ac640d75)。
NV 字段参考：[openpst/libopenpst dm_nv.h](https://github.com/openpst/libopenpst/blob/master/include/qualcomm/dm_nv.h)。
使用上述解析器和本地 Python 检查，未操作实机。

usr_data 使用 ubi-reader 0.8.16 解析，所有操作均离线，未生成或提供刷入命令。
