# QDC507 更新与灾难恢复教程

**刷机前仍然建议完整备份 NAND。**即使默认刷机流程会自动备份，也建议提前独立备份并确认能读取。



## 适用对象

仅限4G 模组 QDC507，固件标识 QDC507GLEFM21，128 MiB NAND：
2048 字节/页、64 页/块、1024 块。不是通用 Quectel EC20/EC25/EG25 固件。
USB 05c6:9008 不能证明型号，须人工确认。实机刷写、坏块行为、启动和联网尚未验证。

默认保留启动链，校验原更新包的七区哈希，只刷五区。
**SBL、MIBIB、TZ、RPM 镜像保留在仓库中，仅在 NAND 内容彻底损坏、确需重建时刷入。**
重建修复的是内容，不是物理损坏的 NAND 芯片。

## 主机准备与离线检查

Linux USB 主机，Python 3.11+、venv 和 libusb。WSL 须正确透传 USB；原生 Windows 未验证。
以下命令不访问 USB：

```sh
python3 scripts/recovery.py verify
python3 scripts/recovery.py plan
python3 scripts/recovery.py flash
```

plan/flash 默认仅预览五区更新。安装 EDL 依赖（需要网络，可沿用代理）：

Git 克隆需初始化子模块；本项目候选 ZIP 已附必要源码，可跳过第一行。

```sh
git submodule update --init vendor/edl
python3 -m venv .venv
.venv/bin/python -m pip install -r vendor/edl/requirements.txt
```

依赖未全部锁版本，安装或解析失败时停止。不要直接运行 vendor/edl/edl.py 或 edl_guard.py；
实际操作统一使用 recovery.py。本流程不使用 qfil、rawxml 或整片写入。

## 进入 EDL 与备份

刷机前仍然建议完整备份 NAND。操作准备、产物、校验和保存方法见[完整 NAND 备份教程](BACKUP.md)。

核对型号，拔掉其他 Qualcomm 9008 设备，使用该模块已确认的维修方法进入 EDL。
脚本只接受恰好一台 05c6:9008 设备。不提供猜测的测试点或自动更改 USB 配置的命令。
按主机环境设置 USB 权限；需要 root 时使用虚拟环境 Python 的绝对路径。

备份到仓库外、尚不存在的目录：

```sh
.venv/bin/python scripts/recovery.py backup --output ../private-qdc507-backup-001
```

双读 128 MiB，大小及 SHA-256 必须一致。读取会装载 RAM loader，不请求擦写 NAND。
备份和日志可能含设备身份，禁止上传。空 NAND 的备份不能替代已丢失的校准数据。

## 默认更新：校验七区，只刷五区

```sh
.venv/bin/python scripts/recovery.py flash --execute --confirm-model QDC507-128MiB --backup-dir ../private-qdc507-before-update-001
```

默认模式为 update，也可以显式指定 --mode update；需要交互输入 `FLASH QDC507`。

1. 校验包内文件、loader、XML 和固定分区范围。
2. 双读备份、核验 NAND 几何；读取不稳定则停止。
3. 对 SBL、MIBIB、sec、TZ、RPM、machine、misc 七区计算 SHA-256，与原更新包 compatibility 清单逐项比较。
4. 任何一项不匹配，在首次擦写前停止，不自动修复或切换模式。
5. 仅对 RAWDATA、boot、recoveryfs、system、aboot 逐区擦除、写入、回读。
6. 再读整片，检查五区正确、其余十区与刷前逐字节一致，不自动重启。

哈希失败可能是型号、版本、布局不兼容或损坏；**不能仅为绕过错误使用重建模式**。
默认模式下，空 MIBIB 也不能通过七区哈希检查。

## 仅限 NAND 内容彻底损坏：重建模式

必须确认是上述型号和几何规格、确有灾难性内容损坏、需要重建。
此模式不适用于日常升级，也不会恢复缺失的身份和校准数据。

先离线预览：

```sh
.venv/bin/python scripts/recovery.py plan --mode nand-rebuild
```

实际执行：

```sh
.venv/bin/python scripts/recovery.py flash --mode nand-rebuild --execute --confirm-model QDC507-128MiB --backup-dir ../private-qdc507-before-rebuild-001
```

依次输入 `FLASH QDC507` 和 `REBUILD DESTROYED NAND`。
七区哈希前置条件不适用于已经损毁的内容；此模式单独检查几何，仍双读备份。
MIBIB 全 FF 或表头已无法识别时允许重建；若存在可识别但与本包不符的分区表，拒绝继续。

按 RAWDATA、boot、recoveryfs、system、RPM、TZ、aboot、MIBIB、SBL 顺序逐区擦写和回读。
最终验证九区正确、其余六区不变。
**EFS2、sys_rev、usr_data、sec、machine、misc 两种模式下都不擦写。**

丢失的校准/身份数据需要原设备备份或厂商流程；本项目不提供导入他机数据的步骤。
usr_data 能否被固件完整初始化也未实测。仅刷本包不保证正常启动、入网或射频功能。

## 失败与 XML

任意回读失败、几何无法确认、操作无成功回执或保护区变化均停止。
不自动回滚、重试或重启，保留外部备份和日志。每次发送前再次检查当前模式的精确地址。
loader 不支持 erase 时拒绝执行，禁止以写零模拟擦除；不存在整片擦除开关。

- firmware/rawprogram_qdc507_public.xml：默认五区映射。
- firmware/rawprogram_qdc507_nand_rebuild_only.xml：仅限彻底损坏时的九区重建映射。

镜像路径均相对 firmware/。XML 自身不执行哈希前置检查、人工确认或回读保护，
不得绕开 recovery.py 直接执行，也不宣称为已验证的 QFIL 流程。
MIBIB 镜像是设备分区表，XML 是主机端指令。没有依据要求 patch.xml，故不提供。

镜像仅含页正文，不含 OOB，不是硬件编程器可直接使用的正文加 OOB 转储。
ECC 和坏块映射由控制器/loader 处理，地址白名单不能替代真实硬件验证。
