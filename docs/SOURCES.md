# 来源与许可证

## Firehose

- 上游：https://github.com/Biktorgj/quectel_eg25_recovery
- 固定提交：`8b89b7d9ecf4af74674eb56c62aad8ca3f69aece`
- 路径：`update/firehose/prog_nand_firehose_9x07.mbn`
- 原始下载：https://raw.githubusercontent.com/Biktorgj/quectel_eg25_recovery/8b89b7d9ecf4af74674eb56c62aad8ca3f69aece/update/firehose/prog_nand_firehose_9x07.mbn
- 文件大小：128376；SHA-256：`2e32df166a2d67facf500db19e1b741d11d1f183aa8decb2c944319da88a41b6`

独立下载和本地 loader 的哈希一致。未修改 loader。
数字签名/公钥证书不等于签名私钥，也不构成再分发许可证；签名信任链未在本项目中验证。
目前未确认上述二进制的厂商再分发授权。公开仓库的存在本身不解决该授权问题。

## 固件

来源于QDC507GLEFM21_01.001.02.004设备备份

原更新包写入 RAWDATA、aboot、boot、recoveryfs、system。
SBL、MIBIB、TZ、RPM 为重建补充素材，四区 SHA-256 均符合该更新包 compatibility 清单；
不属于默认五区更新载荷。这不是所有硬件批次通用的证明。
九区逐文件哈希见 firmware/manifest.json。二进制权利归对应权利人，
本项目不对它们重新授予 GPL 或其他开源许可。

## EDL 与自编脚本

`vendor/edl` 是 [bkerler/edl](https://github.com/bkerler/edl) 的 Git 子模块。
固定提交：`1cda1a616748d608667b2d13b73a28d3197ceb45`。上游源码未修改，许可证见 vendor/edl/LICENSE。
NAND 的 PAGES_PER_BLOCK 支持由该上游提交提供。范围保护在 scripts/edl_guard.py 中实现。
上游通用入口本身没有本项目保护，禁止绕过 recovery.py 直接操作设备。

Git 仓库通过 gitlink 固定版本；审核 ZIP 仅附同一提交的运行所需 Python 文件及许可证，
按 PUBLIC_FILES.sha256 核验，不附整个上游工具集或 Loaders 库。
本项目新编写的脚本按 GPL-3.0-only 提供，根目录 LICENSE 保存完整许可证。
此许可不覆盖 firmware/ 内的第三方二进制。未改动或移除其签名及权利标记。
