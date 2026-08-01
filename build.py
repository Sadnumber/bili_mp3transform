"""
一键打包脚本：把项目 + Python 运行时 + ffmpeg 打包成单个 exe。

用法：
    python build.py                # 自动准备 ffmpeg 并打包
    python build.py --ffmpeg <路径> # 指定本机 ffmpeg.exe
    python build.py --onedir       # 打包成目录（启动更快，体积略大）

产物：dist/B站缓存转换器.exe
"""
import os
import sys
import shutil
import zipfile
import argparse
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(ROOT, 'bin')
FFMPEG_LOCAL = os.path.join(BIN_DIR, 'ffmpeg.exe')
APP_NAME = 'B站缓存转换器'

# gyan.dev 的 essentials 构建，体积最小（含 libmp3lame）
FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
FFMPEG_URL_FALLBACK = (
    'https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip'
)


def log(msg):
    print(f'[build] {msg}', flush=True)


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        log('PyInstaller 已安装')
        return True
    except ImportError:
        pass
    log('正在安装 PyInstaller …')
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    return r.returncode == 0


def _download(url, dest):
    log(f'下载 {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, 'wb') as f:
        total = int(resp.headers.get('Content-Length') or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f'\r  {done / 1048576:.1f}/{total / 1048576:.1f} MB', end='')
        print()


def ensure_ffmpeg(user_path=None):
    """确保 bin/ffmpeg.exe 存在，返回其路径。"""
    os.makedirs(BIN_DIR, exist_ok=True)
    if os.path.isfile(FFMPEG_LOCAL):
        log(f'已存在 {FFMPEG_LOCAL}')
        return FFMPEG_LOCAL

    if user_path and os.path.isfile(user_path):
        shutil.copy2(user_path, FFMPEG_LOCAL)
        log(f'已复制指定的 ffmpeg -> {FFMPEG_LOCAL}')
        return FFMPEG_LOCAL

    zip_path = os.path.join(BIN_DIR, '_ffmpeg.zip')
    for url in (FFMPEG_URL, FFMPEG_URL_FALLBACK):
        try:
            _download(url, zip_path)
            break
        except Exception as e:
            log(f'下载失败: {e}')
    else:
        # 全部下载失败，回退到 PATH 中的 ffmpeg
        found = shutil.which('ffmpeg')
        if found:
            shutil.copy2(found, FFMPEG_LOCAL)
            log(f'使用系统 ffmpeg -> {FFMPEG_LOCAL}')
            return FFMPEG_LOCAL
        raise RuntimeError('无法获取 ffmpeg，请手动放置 bin/ffmpeg.exe 后重试。')

    log('解压 ffmpeg …')
    with zipfile.ZipFile(zip_path) as z:
        member = next((n for n in z.namelist() if n.endswith('bin/ffmpeg.exe')), None)
        if not member:
            raise RuntimeError('压缩包内未找到 ffmpeg.exe')
        with z.open(member) as src, open(FFMPEG_LOCAL, 'wb') as dst:
            shutil.copyfileobj(src, dst)
    os.remove(zip_path)
    log(f'已就绪 {FFMPEG_LOCAL} ({os.path.getsize(FFMPEG_LOCAL) / 1048576:.1f} MB)')
    return FFMPEG_LOCAL


def build(onedir=False):
    for d in ('build', 'dist'):
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)

    args = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean',
        '--windowed',
        '--name', APP_NAME,
        '--add-binary', f'{FFMPEG_LOCAL}{os.pathsep}bin',
        '--hidden-import', 'tkinter',
        '--exclude-module', 'numpy',
        '--exclude-module', 'PIL',
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'pytest',
        '--exclude-module', 'setuptools',
        '--exclude-module', 'pip',
    ]
    icon = os.path.join(ROOT, 'app.ico')
    if os.path.isfile(icon):
        args += ['--icon', icon]
    args += ['--onedir'] if onedir else ['--onefile']
    args += [os.path.join(ROOT, 'app.py')]

    log('开始打包 …')
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit('打包失败')

    out = os.path.join(ROOT, 'dist', APP_NAME + ('' if onedir else '.exe'))
    log(f'打包完成: {out}')
    if os.path.isfile(out):
        log(f'体积: {os.path.getsize(out) / 1048576:.1f} MB')


def main():
    ap = argparse.ArgumentParser(description='打包 B站缓存转换器为独立 exe')
    ap.add_argument('--ffmpeg', help='本机 ffmpeg.exe 路径（可选）')
    ap.add_argument('--onedir', action='store_true', help='打包为目录而非单文件')
    a = ap.parse_args()

    if os.name != 'nt':
        log('警告：非 Windows 环境无法产出 Windows exe。')
    if not ensure_pyinstaller():
        raise SystemExit('PyInstaller 安装失败')
    ensure_ffmpeg(a.ffmpeg)
    build(a.onedir)


if __name__ == '__main__':
    main()
