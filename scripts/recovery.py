#!/usr/bin/env python3
"""QDC507 固件恢复入口；默认离线预览，不支持整片擦除。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PAGE = 2048
BLOCK = 131072
TOTAL = 134217728
# 固定布局不从用户可编辑的 XML/manifest 读取，避免误扩大写入范围。
LAYOUT = (
    ('SBL', 0, 10), ('MIBIB', 10, 10), ('EFS2', 20, 136),
    ('sys_rev', 156, 26), ('RAWDATA', 182, 4), ('sec', 186, 4),
    ('TZ', 190, 12), ('RPM', 202, 5), ('machine', 207, 5),
    ('aboot', 212, 10), ('boot', 222, 43), ('misc', 265, 4),
    ('recoveryfs', 269, 42), ('usr_data', 311, 168), ('system', 479, 545),
)
PROTECTED = frozenset({'EFS2', 'sys_rev', 'usr_data', 'sec', 'machine', 'misc'})
ORDER = ('RAWDATA', 'boot', 'recoveryfs', 'system', 'RPM', 'TZ', 'aboot', 'MIBIB', 'SBL')
UPDATE_ORDER = tuple(name for name in ORDER if name not in {'SBL', 'MIBIB', 'TZ', 'RPM'})
COMPATIBILITY = frozenset({'SBL', 'MIBIB', 'sec', 'TZ', 'RPM', 'machine', 'misc'})
REGIONS = {name: (start * BLOCK, count * BLOCK) for name, start, count in LAYOUT}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_order(mode='update'):
    require(mode in {'update', 'nand-rebuild'}, '未知刷写模式')
    return UPDATE_ORDER if mode == 'update' else ORDER


def permitted_range(start_sector, size, mode='update'):
    """默认仅允许五区；显式 NAND 重建模式才允许另外四区。"""
    for name in write_order(mode):
        if REGIONS[name] == (start_sector * PAGE, size):
            return name
    raise ValueError('禁止此写入/擦除范围：当前模式不允许、涉及保护区、整片或非完整分区')


def checked_path(root, relative):
    p = Path(relative)
    require(not p.is_absolute() and '..' not in p.parts, '非法包内路径')
    target = root / p
    require(not target.is_symlink() and target.resolve().is_relative_to(root.resolve()), '禁止链接逃逸')
    require(target.is_file(), f'缺少文件：{relative}')
    return target


def verify(root=ROOT):
    """核验所有公开文件及 XML，整个过程不导入 USB 库。"""
    sums = root / 'PUBLIC_FILES.sha256'
    seen = set()
    for line in sums.read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        require(name not in seen, '重复文件条目')
        seen.add(name)
        require(digest(checked_path(root, name)) == expected, f'文件校验失败：{name}')
    m = json.loads((root / 'firmware/manifest.json').read_text())
    require(m['model'] == 'QDC507-128MiB', '型号不符')
    require({p['name'] for p in m['partitions']} == set(ORDER), '分区白名单不符')
    require(len(m['partitions']) == len(ORDER), '重复分区')
    for p in m['partitions']:
        require((p['offset'], p['size']) == REGIONS[p['name']], '分区范围不符')
        require(p['file'] == f"firmware/images/{p['name']}.bin", '分区文件路径不符')
        f = checked_path(root, p['file'])
        require(f.stat().st_size == p['size'] and digest(f) == p['sha256'], '镜像校验失败')
    loader = checked_path(root, m['loader']['file'])
    require(digest(loader) == m['loader']['sha256'], 'loader 校验失败')
    require(not list((root / 'firmware').rglob('full-nand*')), '公开包不得包含整片镜像')
    require(len(m['compatibility']) == 7 and {p['name'] for p in m['compatibility']} == COMPATIBILITY,
            '七区兼容性清单不符')
    for p in m['compatibility']:
        require((p['offset'], p['size']) == REGIONS[p['name']], '兼容性分区范围不符')
    verify_xml(root, 'firmware/rawprogram_qdc507_public.xml', 'update')
    verify_xml(root, 'firmware/rawprogram_qdc507_nand_rebuild_only.xml', 'nand-rebuild')
    return m


def verify_xml(root, filename, mode):
    order = write_order(mode)
    xml = ET.parse(root / filename).getroot()
    require(xml.tag == 'data' and len(xml) == len(order) * 2, 'XML 条目数不符')
    for i, name in enumerate(order):
        start, size = REGIONS[name]
        for e, tag in [(xml[2*i], 'erase'), (xml[2*i+1], 'program')]:
            require(e.tag == tag and e.get('label') == name, 'XML 次序或名称不符')
            require(int(e.get('start_sector')) * PAGE == start, 'XML 起点不符')
            require(int(e.get('num_partition_sectors')) * PAGE == size, 'XML 长度不符')
            require(int(e.get('SECTOR_SIZE_IN_BYTES')) == PAGE, 'XML 页大小不符')
            require(int(e.get('PAGES_PER_BLOCK')) == 64, 'XML 块大小不符')
            require(int(e.get('physical_partition_number')) == 0, 'XML 闪存编号不符')
            permitted_range(int(e.get('start_sector')), size, mode)
        require(xml[2*i+1].get('filename') == f'images/{name}.bin', 'XML 文件名不符')


def check_compatibility(data, manifest):
    require(len(data) == TOTAL, '备份长度不符')
    failed = []
    for p in manifest['compatibility']:
        offset, size = REGIONS[p['name']]
        if hashlib.sha256(data[offset:offset+size]).hexdigest() != p['sha256']:
            failed.append(p['name'])
    require(not failed, '七区兼容性哈希不匹配，未执行任何擦写：' + ', '.join(failed))


def check_layout(data, expected_mibib, allow_damaged=False):
    """只允许同一分区表，或全部为空的 MIBIB 区域；不接受未知布局。"""
    offset, size = REGIONS['MIBIB']
    current = data[offset:offset+size]
    require(len(data) == TOTAL, '备份长度不符')
    if current == b'\xff' * size:
        return 'blank-mibib'
    # 忽略分区表之外的运行时冗余数据，仅比较已确认的 MIBIB 表头和 15 个条目。
    magic = bytes.fromhex('aa73ee55 dbbd5ee3')
    reference = expected_mibib.find(magic)
    actual = current.find(magic)
    if actual < 0 and allow_damaged:
        return 'damaged-mibib'
    require(reference >= 0 and actual >= 0, '未找到 MIBIB 分区表魔数')
    table_len = 16 + 15 * 28
    require(current[actual:actual+table_len] == expected_mibib[reference:reference+table_len],
            '目标分区表不匹配；拒绝覆盖未知布局')
    return 'matching-mibib'


def private_directory(path):
    p = Path(path).resolve()
    require(not p.is_relative_to(ROOT), '备份/日志目录必须位于本仓库之外')
    p.mkdir(parents=True, exist_ok=False)
    return p


def run_edl(args, output, number, mode='update'):
    """独立受限入口再次检查范围和设备几何；日志只写入外部私有目录。"""
    write_order(mode)
    command = [sys.executable, str(ROOT / 'scripts/edl_guard.py'), '--mode', mode, *map(str, args)]
    result = subprocess.run(command, cwd=output, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=1800)
    (output / f'{number:02d}-{args[0]}.log').write_text(result.stdout, encoding='utf-8')
    require(result.returncode == 0 and 'QDC507_COMMAND_OK' in result.stdout.splitlines(),
            f'EDL {args[0]} 未确认成功；查看 {output} 内日志')
    return result.stdout


def read_twice(output):
    a, b = output / 'full-nand.bin', output / 'full-nand-verify.bin'
    for i, target in enumerate([a, b]):
        run_edl(['rs', '0', str(TOTAL // PAGE), str(target)], output, i)
        require(target.stat().st_size == TOTAL, '读取长度不符')
    sha = digest(a)
    require(sha == digest(b), '两次读取不同；停止，不能使用不稳定备份继续刷写')
    (output / 'backup-manifest.json').write_text(json.dumps({
        'status': 'double-read-verified', 'memory': 'NAND', 'size': TOTAL,
        'page_size': PAGE, 'pages_per_block': BLOCK // PAGE, 'oob_included': False,
        'loader_sha256': digest(ROOT / 'firmware/loader/prog_nand_firehose_9x07.mbn'),
        'copies': [{'file': p.name, 'size': p.stat().st_size, 'sha256': sha} for p in (a, b)],
    }, indent=2) + '\n', encoding='utf-8')
    (output / 'SHA256SUMS').write_text(''.join(f'{sha}  {p.name}\n' for p in (a, b)))
    return a.read_bytes()


def flash(output, confirm, mode='update'):
    manifest = verify()
    order = write_order(mode)
    preserved = set(REGIONS) - set(order)
    require(confirm == 'QDC507-128MiB', '必须明确确认型号 QDC507-128MiB')
    require(sys.stdin.isatty(), '真实刷写必须在交互式终端确认')
    print(f'模式 {mode}：将擦写 {len(order)} 区，保留 {len(preserved)} 区。实机流程尚未验证。')
    require(input('确认目标为QDC507 128MiB，输入 FLASH QDC507：') == 'FLASH QDC507', '已取消')
    if mode == 'nand-rebuild':
        print('仅限 NAND 内容彻底损坏、确需重建。哈希不匹配本身不是启用理由；不修复物理坏芯片。')
        require(input('确认该损坏情形，输入 REBUILD DESTROYED NAND：') == 'REBUILD DESTROYED NAND', '已取消重建')
    output = private_directory(output)
    before = read_twice(output)
    if mode == 'update':
        check_compatibility(before, manifest)
        print('七区兼容性 SHA-256 全部匹配；仅更新五区。')
    else:
        status = check_layout(before, (ROOT / 'firmware/images/MIBIB.bin').read_bytes(), allow_damaged=True)
        print('分区表检查：', status, '；重建不会恢复缺失的身份/校准数据。')
    for i, name in enumerate(order):
        start, size = REGIONS[name]
        image = ROOT / f'firmware/images/{name}.bin'
        print('正在处理：', name, flush=True)
        run_edl(['es', str(start // PAGE), str(size // PAGE)], output, 2+i*3, mode=mode)
        run_edl(['ws', str(start // PAGE), str(image)], output, 3+i*3, mode=mode)
        readback = output / f'{name}-readback.bin'
        run_edl(['rs', str(start // PAGE), str(size // PAGE), str(readback)], output, 4+i*3, mode=mode)
        require(digest(readback) == digest(image), f'{name} 回读不一致；立即停止')
    after_file = output / 'after-full-nand.bin'
    run_edl(['rs', '0', str(TOTAL // PAGE), str(after_file)], output, 40, mode=mode)
    after = after_file.read_bytes()
    require(len(after) == TOTAL, '最终回读长度不符')
    for name in preserved:
        offset, size = REGIONS[name]
        require(before[offset:offset+size] == after[offset:offset+size], f'保护区 {name} 发生变化！停止，不重启')
    for name in order:
        offset, size = REGIONS[name]
        require(after[offset:offset+size] == (ROOT / f'firmware/images/{name}.bin').read_bytes(),
                f'最终整片回读中的 {name} 不一致')
    (output / 'result.json').write_text(json.dumps(dict(status='readback-verified',
        mode=mode, written_partitions=list(order), preserved_partitions=sorted(preserved),
        protected_partitions_unchanged=True, boot_tested=False), indent=2)+'\n')
    print(f'{len(order)} 区回读一致，{len(preserved)} 区与刷前相同。未自动重启；启动和联网仍需人工检查。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('verify', help='离线校验，不访问 USB')
    plan = sub.add_parser('plan', help='列出写入范围，不访问 USB')
    plan.add_argument('--mode', choices=['update', 'nand-rebuild'], default='update')
    backup = sub.add_parser('backup', help='EDL 双份只读 NAND 备份')
    backup.add_argument('--output', required=True)
    f = sub.add_parser('flash', help='默认只预览；真实刷写需要 --execute 和交互确认')
    f.add_argument('--execute', action='store_true')
    f.add_argument('--confirm-model')
    f.add_argument('--backup-dir')
    f.add_argument('--mode', choices=['update', 'nand-rebuild'], default='update')
    args = parser.parse_args()
    verify()
    if args.action == 'verify':
        print('PASS：公开文件哈希、九分区布局、XML 和 loader 均符合清单。')
    elif args.action == 'backup':
        target = private_directory(args.output)
        read_twice(target)
        print('双份备份一致：', target)
    elif args.action == 'flash' and args.execute:
        require(args.backup_dir, '--execute 必须指定仓库外的全新 --backup-dir')
        flash(args.backup_dir, args.confirm_model, args.mode)
    else:
        mode = getattr(args, 'mode', 'update')
        order = write_order(mode)
        print('模式：', mode)
        if mode == 'update':
            print('写前必须匹配的七区 SHA-256：', ', '.join(sorted(COMPATIBILITY)))
        else:
            print('仅限 NAND 内容彻底损坏时重建；不能作为哈希失败的强制继续选项。')
        for name in order:
            offset, size = REGIONS[name]
            print(f'{name:12} offset=0x{offset:08x} size=0x{size:08x} erase/program/readback')
        print('不擦写：', ', '.join(sorted(set(REGIONS)-set(order))))
        print('仅预览：没有连接 USB，没有擦写。')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('失败：', exc, file=sys.stderr)
        sys.exit(1)
