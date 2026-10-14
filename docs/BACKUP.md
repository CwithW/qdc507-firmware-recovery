# 完整 NAND 备份


适用于 QDC507 / QDC507GLEFM21 的已确认 128 MiB NAND 布局。
即使默认刷机流程会自动备份，也建议提前独立备份并确认能读取。

## 准备

Linux USB 主机、Python 3.11+、libusb、至少 512 MiB 可用空间。
WSL 需先正确透传 USB。只连接一台目标设备，核对型号与 NAND 容量。
按该设备已确认的维修方式进入 EDL，使用 `lsusb -d 05c6:9008` 检查枚举。
9008 ID 不能证明型号。脚本不自动修改 USB 配置、不执行重启或猜测测试点。
按系统规则设置 USB 访问权限，必要时使用虚拟环境 Python 的绝对路径。

从 Git 获取的仓库需初始化子模块；本项目候选 ZIP 已附必要源码，可跳过此命令：

```sh
git submodule update --init vendor/edl
python3 -m venv .venv
.venv/bin/python -m pip install -r vendor/edl/requirements.txt
.venv/bin/python scripts/recovery.py verify
```

不要使用 `--remote` 或递归下载 Loaders；本包已有固定 Firehose。
依赖安装需要网络；已在本机全新 Python 3.12 虚拟环境验证安装和导入，未验证其他主机或实机读取。

## 双读备份

在仓库根目录执行，输出目录必须在仓库之外且尚不存在：

```sh
.venv/bin/python scripts/recovery.py backup --output ../private-qdc507-backup-001
```

流程沿用完整 NAND 页正文读取方式：指定 Firehose、NAND、2048 字节/页、64 页/块，
检查 1024 块几何；从第 0 页读取 65536 页，每份为 134217728 字节。
读取两次并比较 SHA-256；任一读取失败、长度不符或内容不同均停止，不能据此继续刷写。
备份不依赖七区兼容性哈希，因而也能保存内容损坏的 NAND；仍须确认相同硬件与几何。
只执行读取，不发出擦除/写入请求；会向设备 RAM 装载 loader。

成功后输出目录包含：

- `full-nand.bin`：第一份完整页正文备份。
- `full-nand-verify.bin`：第二份独立读取，必须与第一份相同。
- `backup-manifest.json`：成功状态、几何、loader 哈希和两份文件校验值。
- `SHA256SUMS`：供再次校验的文件清单。
- `00-rs.log`、`01-rs.log`：两次读取日志。

再次检查文件是否损坏：

```sh
(cd ../private-qdc507-backup-001 && sha256sum -c SHA256SUMS)
```

仅命令成功且两份校验通过才是本流程的有效备份。失败时保留日志排查，换用新的输出目录重试；
不覆盖旧备份。双读一致仅证明两次读取稳定，不保证原固件、校准数据本身完好。

## 保存与恢复边界

备份涵盖十五区，包括 EFS2、sys_rev、usr_data 等设备身份、校准和用户数据。
备份、哈希清单及日志均应私密保存，建议另存一份到独立介质，禁止放进公开 Git 仓库。

本备份不含 OOB/ECC，不能当作硬件编程器所需的正文加 OOB 原始转储。
ECC 与坏块映射由控制器/loader 处理，尚未验证所有坏块场景。
公开恢复脚本只写许可范围，不提供整片备份回灌入口；不能使用其 XML 覆盖校准区。
保留完整备份供针对原设备的后续恢复使用。空 NAND 的备份不能恢复此前已丢失的校准数据。
