"""
发布 GitHub Release 并上传 exe 资产。

用法：
    set GITHUB_TOKEN=ghp_xxx
    python release.py --tag v1.0.0

参数：
    --tag       版本标签，默认 v1.0.0
    --file      要上传的文件，默认 dist/B站缓存转换器.exe
    --repo      仓库 owner/name，默认从 git remote 自动解析
    --draft     创建为草稿，不直接公开
    --prerelease 标记为预发布
"""
import os
import re
import sys
import json
import argparse
import subprocess
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://api.github.com'
DEFAULT_ASSET = os.path.join(ROOT, 'dist', 'B站缓存转换器.exe')


def log(msg):
    print(f'[release] {msg}', flush=True)


def detect_repo():
    """从 git remote 解析 owner/repo。"""
    try:
        url = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return None
    m = re.search(r'github\.com[:/]([^/]+)/(.+?)(?:\.git)?$', url)
    return f'{m.group(1)}/{m.group(2)}' if m else None


def get_token():
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        raise SystemExit(
            '未找到 token。请先设置环境变量：\n'
            '  PowerShell:  $env:GITHUB_TOKEN = "ghp_xxx"\n'
            '  CMD:         set GITHUB_TOKEN=ghp_xxx\n'
            'token 需要 repo (或 Contents: Read and write) 权限。'
        )
    return token


def api(method, url, token, data=None, headers=None, binary=None, content_type=None):
    h = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'bili-mp3transform-release',
    }
    if headers:
        h.update(headers)
    body = binary if binary is not None else (
        json.dumps(data).encode('utf-8') if data is not None else None)
    if content_type:
        h['Content-Type'] = content_type
    elif data is not None:
        h['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')
        raise SystemExit(f'GitHub API {method} {url} 失败: {e.code}\n{detail}')


def ensure_tag_pushed(tag):
    """确保本地已打 tag 并推送到远程。"""
    exists = subprocess.run(['git', 'tag', '-l', tag], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    if not exists:
        log(f'创建标签 {tag}')
        subprocess.run(['git', 'tag', '-a', tag, '-m', f'Release {tag}'],
                       cwd=ROOT, check=True)
    log(f'推送标签 {tag}')
    subprocess.run(['git', 'push', 'origin', tag], cwd=ROOT, check=False)


def find_release(repo, tag, token):
    try:
        return api('GET', f'{API}/repos/{repo}/releases/tags/{tag}', token)
    except SystemExit:
        return None


def build_notes(tag, asset_size_mb):
    return f"""## B站缓存转换器 {tag}

将 B 站客户端下载的 m4s 缓存一键转换为 **MP3 音频** 或 **带声音的完整 MP4 视频**。

### 下载即用
直接下载下方的 `B站缓存转换器.exe`（约 {asset_size_mb:.1f} MB），双击运行即可。
**内置 Python 运行时与 ffmpeg，无需安装任何环境**，支持 Windows 10 / 11 (x64)。

### 使用方法
1. 首次打开设置 **B站缓存目录**（客户端「设置 → 下载设置」中可查看，程序会自动尝试猜测）。
2. 可选设置输出目录、MP3 码率、是否清理中间文件等。
3. 点击 **转换为音频 (MP3)** 或 **转换为完整视频 (MP4)**。

设置会自动保存，下次无需重复配置。程序不修改原始缓存文件。

### 本次更新
- 新增图形界面，无需命令行操作
- 内置 ffmpeg，开箱即用
- 音视频流识别扩展为 `302xx` / `300xx` 前缀匹配，无法识别时按文件体积回退判断
- 标题解析兼容旧版客户端的 `entry.json`（含分 P 名称）
- 处理前先复制缓存到输出目录，不改动原始文件
- 转换在后台线程执行，界面不卡顿且可中途停止

### 说明
- 程序未做代码签名，首次运行 Windows SmartScreen 可能提示「未知发布者」，点击「更多信息 → 仍要运行」即可。
- 仅适用于 x64 架构；ARM 版 Windows 需自行用 `python build.py` 重新打包。
"""


def upload_asset(repo, release, path, token):
    name = os.path.basename(path)
    # 同名资产先删除，避免 422 冲突
    for a in release.get('assets', []):
        if a['name'] == name:
            log(f'删除已存在的同名资产 {name}')
            api('DELETE', f'{API}/repos/{repo}/releases/assets/{a["id"]}', token)

    size = os.path.getsize(path)
    log(f'上传 {name} ({size / 1048576:.1f} MB) …')
    upload_url = release['upload_url'].split('{')[0]
    with open(path, 'rb') as f:
        blob = f.read()
    quoted = urllib.request.quote(name)
    result = api('POST', f'{upload_url}?name={quoted}', token,
                 binary=blob, content_type='application/octet-stream')
    log(f'上传完成: {result.get("browser_download_url")}')
    return result


def main():
    ap = argparse.ArgumentParser(description='发布 GitHub Release')
    ap.add_argument('--tag', default='v1.0.0', help='版本标签，默认 v1.0.0')
    ap.add_argument('--file', default=DEFAULT_ASSET, help='上传的资产文件')
    ap.add_argument('--repo', default=None, help='owner/repo，默认自动解析')
    ap.add_argument('--draft', action='store_true', help='创建为草稿')
    ap.add_argument('--prerelease', action='store_true', help='标记为预发布')
    a = ap.parse_args()

    asset = os.path.abspath(a.file)
    if not os.path.isfile(asset):
        raise SystemExit(f'找不到文件: {asset}\n请先运行 python build.py 打包。')

    repo = a.repo or detect_repo()
    if not repo:
        raise SystemExit('无法解析仓库地址，请用 --repo owner/name 指定。')
    token = get_token()
    log(f'仓库: {repo}  标签: {a.tag}')

    ensure_tag_pushed(a.tag)

    release = find_release(repo, a.tag, token)
    if release:
        log(f'Release {a.tag} 已存在，将更新其资产')
    else:
        log(f'创建 Release {a.tag}')
        release = api('POST', f'{API}/repos/{repo}/releases', token, data={
            'tag_name': a.tag,
            'name': f'B站缓存转换器 {a.tag}',
            'body': build_notes(a.tag, os.path.getsize(asset) / 1048576),
            'draft': a.draft,
            'prerelease': a.prerelease,
        })

    upload_asset(repo, release, asset, token)
    log(f'完成: {release["html_url"]}')


if __name__ == '__main__':
    main()
