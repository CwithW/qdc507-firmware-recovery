#!/usr/bin/env python3
"""受限 EDL 适配层；不开放整片写入、分区名写入、raw XML 或任意擦除。"""
import runpy
import argparse
import sys
from pathlib import Path

from recovery import ROOT, PAGE, BLOCK, TOTAL, REGIONS, permitted_range, require, verify


def validate_command(args, mode='update'):
    require(bool(args), '缺少 EDL 操作')
    cmd = args[0]
    require(cmd in {'rs', 'ws', 'es'}, '只允许受限的读取/逐分区擦写')
    if cmd == 'rs':
        require(len(args) == 4, 'rs 参数数量错误')
        start, count = int(args[1]), int(args[2])
        require(start >= 0 and count > 0 and (start+count)*PAGE <= TOTAL, '读取越界')
        dest = Path(args[3]).resolve()
        require(not dest.is_relative_to(ROOT) and not dest.exists(), '读取目标必须是仓库外新文件')
    elif cmd == 'es':
        require(len(args) == 3, 'es 参数数量错误')
        permitted_range(int(args[1]), int(args[2])*PAGE, mode)
    else:
        require(len(args) == 3, 'ws 参数数量错误')
        path = Path(args[2]).resolve()
        name = permitted_range(int(args[1]), path.stat().st_size, mode)
        require(path == (ROOT / f'firmware/images/{name}.bin').resolve(), '只能写入已校验的公开固件')
    return cmd


def check_geometry(fh):
    fh.cmd_getstorageinfo()
    require(fh.cfg.MemoryName.lower() == 'nand', '目标不是 NAND')
    require(fh.cfg.total_blocks == 1024 and fh.cfg.block_size == BLOCK and
            fh.cfg.SECTOR_SIZE_IN_BYTES == PAGE, '目标 NAND 几何不匹配或无法确认')


def main():
    verify()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['update', 'nand-rebuild'], default='update')
    parser.add_argument('operation', nargs=argparse.REMAINDER)
    parsed = parser.parse_args()
    args, mode = parsed.operation, parsed.mode
    cmd = validate_command(args, mode)
    vendor = ROOT / 'vendor/edl'
    sys.path.insert(0, str(vendor))
    from edlclient.Library.firehose import firehose
    import usb.core
    devices = list(usb.core.find(find_all=True, idVendor=0x05c6, idProduct=0x9008))
    require(len(devices) == 1, '必须且只能连接一台 05c6:9008 设备')
    # 所有实际写入在发送前再次验证几何与地址，即使上层 CLI 解析行为变化也不放行。
    program, erase, read = firehose.cmd_program, firehose.cmd_erase, firehose.cmd_read
    completed = False

    def guarded_program(self, lun, start, filename, display=True):
        nonlocal completed
        require(cmd == 'ws' and lun == 0, '禁止未请求的 program')
        validate_command(['ws', str(start), str(filename)], mode)
        check_geometry(self)
        result = program(self, lun, start, filename, display)
        completed = bool(result)
        return result

    def guarded_erase(self, lun, start, count, display=True):
        nonlocal completed
        require(cmd == 'es' and lun == 0, '禁止未请求的 erase')
        permitted_range(start, count*PAGE, mode)
        check_geometry(self)
        require('erase' in self.supported_functions, 'loader 不支持 erase；禁止以写零代替擦除')
        result = erase(self, lun, start, count, display)
        completed = bool(result)
        return result

    def guarded_read(self, lun, start, count, filename, display=True):
        nonlocal completed
        require(cmd == 'rs' and lun == 0, '禁止未请求的 read')
        validate_command(['rs', str(start), str(count), str(filename)], mode)
        check_geometry(self)
        result = read(self, lun, start, count, filename, display)
        completed = bool(result)
        return result

    def denied_write(*args, **kwargs):
        raise ValueError('禁止缓冲写入、patch 及未经验证的 XML')

    firehose.cmd_program = guarded_program
    firehose.cmd_erase = guarded_erase
    firehose.cmd_read = guarded_read
    firehose.cmd_program_buffer = denied_write
    firehose.cmd_patch = denied_write
    firehose.cmd_rawxml = denied_write
    firehose.cmd_xml = denied_write
    from edlclient.Library.streaming_client import streaming_client
    streaming_client.handle_streaming = denied_write
    sys.argv = [str(vendor/'edl.py'), *args,
                '--memory=nand', '--sectorsize=2048', '--pagesperblock=64',
                '--vid=0x05c6', '--pid=0x9008',
                '--loader='+str(ROOT/'firmware/loader/prog_nand_firehose_9x07.mbn')]
    try:
        runpy.run_path(str(vendor/'edl.py'), run_name='__main__')
    except SystemExit as exc:
        require(exc.code in (None, 0), '底层 EDL 返回失败')
    require(completed, '底层进程结束，但没有确认请求的操作成功')
    print('QDC507_COMMAND_OK')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('EDL guard 拒绝或失败：', exc, file=sys.stderr)
        sys.exit(1)
