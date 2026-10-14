"""离线测试；不导入 USB 库，不执行实机擦写。"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import recovery as r
import edl_guard as guard


class ProtectionTests(unittest.TestCase):
    def test_public_package(self):
        self.assertEqual(len(r.verify()['partitions']), 9)

    def test_protected_and_whole_chip_rejected(self):
        for name in r.PROTECTED:
            start, size = r.REGIONS[name]
            with self.assertRaises(ValueError):
                r.permitted_range(start//r.PAGE, size)
            with self.assertRaises(ValueError):
                guard.validate_command(['es', str(start//r.PAGE), str(size//r.PAGE)])
        for start, size in [(0,r.TOTAL), (0,r.BLOCK), (0,0), (-1,r.BLOCK), (182*64,r.BLOCK*5)]:
            with self.assertRaises(ValueError):
                r.permitted_range(start, size)

    def test_exact_public_ranges_only(self):
        for name in r.ORDER:
            start, size = r.REGIONS[name]
            self.assertEqual(r.permitted_range(start//r.PAGE,size,'nand-rebuild'), name)
            for bad_start, bad_size in [(start//r.PAGE+1,size),(start//r.PAGE,size+r.PAGE)]:
                with self.assertRaises(ValueError):
                    r.permitted_range(bad_start,bad_size,'nand-rebuild')

    def test_default_guard_rejects_boot_chain(self):
        for name in ['SBL','MIBIB','TZ','RPM']:
            start,size=r.REGIONS[name]
            for args in [['es',str(start//r.PAGE),str(size//r.PAGE)],
                         ['ws',str(start//r.PAGE),str(ROOT/f'firmware/images/{name}.bin')]]:
                with self.assertRaises(ValueError):guard.validate_command(args)
                guard.validate_command(args,'nand-rebuild')

    def test_all_seven_compatibility_hashes_are_checked(self):
        m=r.verify()
        data=bytearray(b'\xff'*r.TOTAL)
        for name in ['SBL','MIBIB','TZ','RPM']:
            start,size=r.REGIONS[name]
            data[start:start+size]=(ROOT/f'firmware/images/{name}.bin').read_bytes()
        r.check_compatibility(data,m)
        for name in r.COMPATIBILITY:
            start,_=r.REGIONS[name]
            data[start]^=1
            with self.assertRaisesRegex(ValueError,name):r.check_compatibility(data,m)
            data[start]^=1

    def test_foreign_image_and_generic_commands_rejected(self):
        for args in [['wf','full.bin'], ['qfil','x','y','z'], ['rawxml','<data/>'], ['reset']]:
            with self.assertRaises(ValueError):
                guard.validate_command(args)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'SBL.bin'
            p.write_bytes((ROOT/'firmware/images/SBL.bin').read_bytes())
            with self.assertRaises(ValueError):
                guard.validate_command(['ws','0',str(p)])

    def test_no_private_partitions_in_files(self):
        files={p.stem for p in (ROOT/'firmware/images').iterdir()}
        self.assertEqual(files,set(r.ORDER))
        entries=[line.split('  ',1)[1] for line in (ROOT/'PUBLIC_FILES.sha256').read_text().splitlines()]
        self.assertFalse(any(Path(s).suffix.lower() in {'.qcn','.xqcn','.log'} for s in entries))
        self.assertFalse(any('full-nand' in Path(s).name for s in entries))

    def test_reference_partitions_cannot_be_flashed(self):
        reference = ROOT / 'reference/calibration'
        report = json.loads((reference / 'sanitization.json').read_text())
        self.assertEqual({p['name'] for p in report['partitions']}, {'EFS2', 'sys_rev'})
        for p in report['partitions']:
            image = reference / p['file']
            start, size = r.REGIONS[p['name']]
            self.assertEqual(image.stat().st_size, size)
            self.assertEqual(r.digest(image), p['sha256'])
            for mode in ('update', 'nand-rebuild'):
                with self.assertRaises(ValueError):
                    guard.validate_command(['ws', str(start // r.PAGE), str(image)], mode)
                with self.assertRaises(ValueError):
                    guard.validate_command(['es', str(start // r.PAGE), str(size // r.PAGE)], mode)

    def test_blank_and_matching_mibib(self):
        m=(ROOT/'firmware/images/MIBIB.bin').read_bytes()
        data=bytearray(b'\xff'*r.TOTAL)
        self.assertEqual(r.check_layout(data,m),'blank-mibib')
        start,size=r.REGIONS['MIBIB']
        data[start:start+size]=m
        self.assertEqual(r.check_layout(data,m),'matching-mibib')
        data[start+2048+16+16]^=1
        with self.assertRaises(ValueError):
            r.check_layout(data,m)

    def test_backup_mismatch_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            def fake(args, output, number):
                Path(args[3]).write_bytes(bytes([number])*32)
            with patch.object(r,'TOTAL',32), patch.object(r,'run_edl',side_effect=fake):
                with self.assertRaisesRegex(ValueError,'两次读取不同'):
                    r.read_twice(Path(temp))
            self.assertFalse((Path(temp) / 'backup-manifest.json').exists())
            self.assertFalse((Path(temp) / 'SHA256SUMS').exists())

    def test_backup_records_verified_copies(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            data = b'Q' * r.PAGE
            def fake(args, folder, number):
                self.assertEqual(args[:3], ['rs', '0', '1'])
                Path(args[3]).write_bytes(data)
            with patch.object(r, 'TOTAL', len(data)), patch.object(r, 'run_edl', side_effect=fake):
                self.assertEqual(r.read_twice(output), data)
            manifest = json.loads((output / 'backup-manifest.json').read_text())
            self.assertEqual(manifest['status'], 'double-read-verified')
            self.assertFalse(manifest['oob_included'])
            for record in manifest['copies']:
                self.assertEqual(r.digest(output / record['file']), record['sha256'])
            self.assertEqual(len((output / 'SHA256SUMS').read_text().splitlines()), 2)

    def test_geometry_mismatch_rejected(self):
        class Config:
            MemoryName='nand';total_blocks=2048;block_size=131072;SECTOR_SIZE_IN_BYTES=2048
        class Device:
            cfg=Config()
            def cmd_getstorageinfo(self):pass
        with self.assertRaises(ValueError):guard.check_geometry(Device())
        Device.cfg.total_blocks=1024
        guard.check_geometry(Device())

    def test_zero_exit_without_acknowledgement_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result=subprocess.CompletedProcess([],0,stdout='No suitable loader found\n')
            with patch.object(r.subprocess,'run',return_value=result):
                with self.assertRaisesRegex(ValueError,'未确认成功'):
                    r.run_edl(['es','0','640'],Path(temp),0)

    def test_private_output_must_stay_outside_repo(self):
        with self.assertRaises(ValueError):r.private_directory(ROOT/'private/test')

    def test_default_flash_does_not_run_edl(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/recovery.py'),'flash'],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('仅预览',result.stdout)
        self.assertEqual(result.stdout.count('erase/program/readback'),5)

    def test_execute_requires_confirmation_before_usb(self):
        with patch.object(sys.stdin,'isatty',return_value=True), \
             patch('builtins.input',return_value='NO'), patch.object(r,'read_twice') as read:
            with self.assertRaises(ValueError):r.flash('/unused','QDC507-128MiB')
            read.assert_not_called()

    def exercise_flash(self, fault=None, mode='update'):
        """用内存 NAND 模型走完整流程，验证失败时停止及保护区比较。"""
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            repo=base/'repo'
            images=repo/'firmware/images'
            images.mkdir(parents=True)
            names=list(r.REGIONS)
            regions={name:(i*32,32) for i,name in enumerate(names)}
            before=bytes([17])*(len(names)*32)
            memory=bytearray(before)
            manifest={'compatibility':[
                {'name':n,'sha256':hashlib.sha256(before[s:s+size]).hexdigest()}
                for n,(s,size) in regions.items() if n in r.COMPATIBILITY]}
            if fault=='compatibility':manifest['compatibility'][0]['sha256']='0'*64
            for name in r.ORDER:
                (images/(name+'.bin')).write_bytes(bytes([names.index(name)+32])*32)
            events=[]
            def simulate(args, output, number, mode='update'):
                events.append(args[0])
                start=int(args[1])
                if args[0]=='es':memory[start:start+int(args[2])]=b'\xff'*int(args[2])
                elif args[0]=='ws':
                    data=Path(args[2]).read_bytes()
                    memory[start:start+len(data)]=data
                    if fault=='readback':memory[start]^=1
                    if fault=='protected':memory[regions['EFS2'][0]]=99
                else:Path(args[3]).write_bytes(memory[start:start+int(args[2])])
            with patch.object(r,'ROOT',repo), patch.object(r,'REGIONS',regions), \
                 patch.object(r,'PAGE',1), patch.object(r,'TOTAL',len(memory)), \
                 patch.object(r,'verify',return_value=manifest), patch.object(r,'read_twice',return_value=before), \
                 patch.object(r,'check_layout',return_value='matching-mibib'), \
                 patch.object(r,'run_edl',side_effect=simulate), \
                 patch.object(sys.stdin,'isatty',return_value=True), \
                 patch('builtins.input',side_effect=['FLASH QDC507','REBUILD DESTROYED NAND']):
                if fault:
                    with self.assertRaisesRegex(ValueError,'回读不一致|保护区 EFS2|兼容性哈希不匹配'):
                        r.flash(base/'private','QDC507-128MiB',mode)
                else:
                    r.flash(base/'private','QDC507-128MiB',mode)
                    for name in set(regions)-set(r.write_order(mode)):
                        start,size=regions[name]
                        self.assertEqual(memory[start:start+size],before[start:start+size])
            return events

    def test_default_simulation_preserves_ten_regions(self):
        self.assertEqual(self.exercise_flash(), ['es','ws','rs']*5+['rs'])

    def test_rebuild_simulation_preserves_six_regions(self):
        self.assertEqual(self.exercise_flash(mode='nand-rebuild'), ['es','ws','rs']*9+['rs'])

    def test_compatibility_failure_never_starts_writes(self):
        self.assertEqual(self.exercise_flash('compatibility'), [])

    def test_rebuild_needs_second_confirmation(self):
        with patch.object(sys.stdin,'isatty',return_value=True), \
             patch('builtins.input',side_effect=['FLASH QDC507','NO']), \
             patch.object(r,'read_twice') as read:
            with self.assertRaisesRegex(ValueError,'已取消重建'):
                r.flash('/unused','QDC507-128MiB','nand-rebuild')
            read.assert_not_called()

    def test_failed_first_readback_stops_remaining_writes(self):
        self.assertEqual(self.exercise_flash('readback'), ['es','ws','rs'])

    def test_final_protected_region_corruption_is_detected(self):
        self.exercise_flash('protected')


if __name__=='__main__':unittest.main()
