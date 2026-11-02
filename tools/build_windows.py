"""Reproducible Windows launcher build. Requires an official Go 1.24+ toolchain."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def build():
    go = os.environ.get('GO_BIN') or shutil.which('go')
    if not go:
        raise SystemExit('Instala el compilador oficial de https://go.dev/dl/ o define GO_BIN.')
    version = subprocess.check_output([go, 'version'], text=True).strip()
    if not version.startswith('go version go'):
        raise SystemExit('GO_BIN debe apuntar al compilador oficial del lenguaje Go.')
    dist = ROOT / 'dist'
    downloads = ROOT / 'downloads'
    dist.mkdir(exist_ok=True); downloads.mkdir(exist_ok=True)
    exe = dist / 'EscuelaTenis.exe'
    environment = {**os.environ, 'GOOS': 'windows', 'GOARCH': 'amd64', 'CGO_ENABLED': '0', 'GOTOOLCHAIN': 'local'}
    subprocess.run([go, 'build', '-trimpath', '-buildvcs=false', '-ldflags=-H=windowsgui -s -w', '-o', str(exe), './launcher'], cwd=ROOT, env=environment, check=True)
    goroot = Path(subprocess.check_output([go, 'env', 'GOROOT'], text=True).strip())
    archive = downloads / 'EscuelaTenis-Windows.zip'
    files = {'EscuelaTenis.exe': exe.read_bytes(), 'LEEME.md': (ROOT / 'WINDOWS.md').read_bytes(), 'GO-LICENSE.txt': (goroot / 'LICENSE').read_bytes()}
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, contents in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o755 if name.endswith('.exe') else 0o644) << 16
            bundle.writestr(entry, contents, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    lines = [f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}' for file in (exe, archive)]
    (downloads / 'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n', encoding='ascii')
    print(version)
    print(f'Windows x64: {exe.stat().st_size:,} bytes; ZIP: {archive.stat().st_size:,} bytes')
    print('\n'.join(lines))


if __name__ == '__main__':
    build()
