# qdc507-firmware-recovery

**UNTESTED：未经实机刷写、启动和联网验证。离线测试通过不代表已验证可用或可安全救砖。**

**刷机前仍然建议完整备份 NAND，并将备份保存在仓库之外。**
备份方法见[完整 NAND 备份教程](docs/BACKUP.md)。

**use at your risk.**

面向 **4G 模组 QDC507、128 MiB NAND**，目标固件为
`QDC507GLEFM21_01.001.02.004`。**不是通用 Quectel EC20/EC25/EG25 刷机包**，
不能只根据 9008 USB ID 或 9x07 芯片型号判断兼容性。尚未完成实机刷写、启动、联网验证。

本仓库保留九个公开固件分区、Firehose loader、分区布局、受限刷机脚本和恢复教程。
恢复固件不包含设备专属分区。独立的 [校准参考目录](reference/calibration/README.md) 提供
移除已识别 IMEI/SN/IMSI/ICCID 后的 EFS2、sys_rev 原始分区副本，仅供参考、禁止刷入，
不构成完整匿名化保证。不附 usr_data、QCN/XQCN、整片 NAND 或私人备份日志。

## 恢复范围

| 模式 | 写入范围 | 前置条件 |
|---|---|---|
| 默认 `update` | RAWDATA、aboot、boot、recoveryfs、system | SBL、MIBIB、sec、TZ、RPM、machine、misc 七区 SHA-256 全部匹配原更新包 |
| 显式 `nand-rebuild` | 默认五区＋SBL、MIBIB、TZ、RPM | 仅在 NAND 内容彻底损坏、确需重建时；独立二次确认 |

**SBL/MIBIB/TZ/RPM 文件保留在仓库，仅在 NAND 内容彻底损坏时刷入，不在默认刷写范围内。**
EFS2、sys_rev、usr_data、sec、machine、misc 两种模式下都不擦写。
七区哈希失败本身不是启用重建模式的理由，也可能是型号/版本不兼容。

**空 NAND：可以补回这九区的固件素材和 MIBIB 分区表，但不能凭空恢复身份、射频校准等数据。**
不承诺空 NAND 只刷本包即可正常启动或联网。缺失的专属数据需原设备备份或厂商维修流程。
本项目不提供导入其他设备身份/校准数据的脚本。用户数据区初始化是否足以恢复运行尚未实测。

**有数据的 NAND：**默认双读备份、验证七区哈希，再逐区擦写五区和回读，
最后检查其余十区与刷前逐字节相同。重建模式写九区、检查其余六区。底层 NAND 坏块映射和 loader 行为仍需实机验证，
地址保护不等于对任何故障条件作不丢数据保证。

## Firehose 上游

本包包含 `firmware/loader/prog_nand_firehose_9x07.mbn`，128,376 字节。
已从独立公开上游下载并确认与包内文件 SHA-256 完全相同：

- 仓库：[Biktorgj/quectel_eg25_recovery](https://github.com/Biktorgj/quectel_eg25_recovery)
- [固定提交下的文件](https://github.com/Biktorgj/quectel_eg25_recovery/blob/8b89b7d9ecf4af74674eb56c62aad8ca3f69aece/update/firehose/prog_nand_firehose_9x07.mbn)
- SHA-256：`2e32df166a2d67facf500db19e1b741d11d1f183aa8decb2c944319da88a41b6`

此链接说明 loader 的公开来源，不表示上游 EG25 整套固件适用于模组，
也不表示已取得厂商二进制再分发许可。见 [来源与许可证](docs/SOURCES.md)。

## 开始

使用 Python 3.11+。Git 克隆后先运行 `git submodule update --init vendor/edl`，不要使用 `--remote` 更新到未经核验的版本。
本仓库使用指定 loader，无需递归下载上游 Loaders 子模块。

以下操作离线，不导入 USB 库，不访问设备：

```sh
python3 scripts/recovery.py verify
python3 scripts/recovery.py plan
python3 scripts/recovery.py flash
python3 -m unittest discover -s tests -v
```

`flash` **默认仅预览**。真实操作见 [恢复教程](docs/RECOVERY.md)。
Linux USB 主机为当前脚本设计目标；WSL 需要先正确透传设备，原生 Windows 流程未验证。

## 目录

```text
firmware/images/         九个固件区，不含六个保护区
firmware/loader/         Firehose loader
firmware/layout.json     全部十五区的名称、偏移、大小，无设备身份数据
firmware/manifest.json   九区与 loader 的来源和校验值
firmware/*public.xml     默认五区映射
firmware/*rebuild_only.xml 仅限 NAND 内容彻底损坏时的九区映射
scripts/                校验、预览、备份、受限刷机、候选包打包
reference/calibration/  脱敏原始分区参考副本，不进入刷写流程
vendor/edl/             上游 bkerler/edl Git 子模块，固定提交
tests/                  离线范围保护和打包测试
docs/                   教程、来源、隐私检查和审核清单
PUBLIC_FILES.sha256     显式发布文件白名单及校验值
```

候选压缩包只从显式白名单生成；备份、日志必须输出到仓库之外。

## 固件来源

来源于QDC507GLEFM21_01.001.02.004设备备份

## 致谢

感谢 [white-alone 的原博客](https://blog.white-alone.com/posts/%E5%A4%A7%E7%96%864G%E6%A8%A1%E7%BB%84%E5%92%8C%E9%97%B2%E9%B1%BC%E4%BC%AA%E5%9F%BA%E7%AB%99%E4%BA%8C%E4%B8%89%E4%BA%8B) 提供的研究与参考。
