#!/usr/bin/env python3
"""仅按显式公开文件清单打包；不使用整个目录或 git archive。"""
import argparse
from pathlib import Path
import zipfile
from recovery import ROOT, checked_path, require, verify

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True)
args = parser.parse_args()
verify()
dest = Path(args.output).resolve()
require(not dest.is_relative_to(ROOT), '发布压缩包须写到仓库外')
files = [line.split('  ', 1)[1] for line in (ROOT/'PUBLIC_FILES.sha256').read_text().splitlines()]
files.append('PUBLIC_FILES.sha256')
with zipfile.ZipFile(dest, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for name in files:
        z.write(checked_path(ROOT, name), 'qdc507-firmware-recovery/'+name)
print('已生成候选压缩包，尚未上传：', dest)
