"""
核心处理逻辑：定位 ffmpeg、扫描 B 站缓存、解密 m4s、转 mp3、合并完整 mp4。

所有函数通过 log 回调输出进度，便于 GUI / CLI 复用。
"""
import os
import sys
import json
import shutil
import subprocess

# Windows 下隐藏 ffmpeg 子进程黑窗
_CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def _noop(msg):
    print(msg)


def app_dir():
    """返回程序所在目录（打包后为 exe 所在目录，源码运行为脚本目录）。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir():
    """返回随程序分发的资源目录（PyInstaller onefile 解压临时目录）。"""
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


def find_ffmpeg():
    """
    按优先级定位 ffmpeg 可执行文件：
    1. 打包内置的 bin/ffmpeg.exe
    2. 程序目录下的 bin/ffmpeg.exe 或 ffmpeg.exe
    3. 系统 PATH
    找不到返回 None。
    """
    exe = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    candidates = [
        os.path.join(resource_dir(), 'bin', exe),
        os.path.join(resource_dir(), exe),
        os.path.join(app_dir(), 'bin', exe),
        os.path.join(app_dir(), exe),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    found = shutil.which(exe)
    return found


def run_ffmpeg(args, log=_noop):
    """执行 ffmpeg 命令，返回 (成功?, stderr)。"""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, '未找到 ffmpeg，可执行文件缺失。'
    try:
        result = subprocess.run(
            [ffmpeg] + args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=_CREATE_NO_WINDOW,
        )
    except OSError as e:
        return False, str(e)
    if result.returncode != 0:
        return False, result.stderr or ''
    return True, result.stderr or ''


# ---------------------------------------------------------------- 命名工具

def safe_filename(name, max_len=80):
    """将任意标题清洗为 Windows/跨平台安全的文件夹或文件名。"""
    if not name:
        return 'untitled'
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, '_')
    name = name.replace('\n', ' ').replace('\r', ' ').strip().strip('.')
    if not name:
        return 'untitled'
    if len(name) > max_len:
        name = name[:max_len].rstrip('. ')
    return name or 'untitled'


def _load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def find_title(directory):
    """
    读取 directory（或其父目录）下的 videoInfo.json / entry.json 的标题，
    返回安全文件夹名；找不到则回退为目录名。
    """
    info = _load_json(os.path.join(directory, 'videoInfo.json'))
    if isinstance(info, dict):
        title = info.get('title') or info.get('groupTitle') or ''
        if title:
            return safe_filename(title)

    # 兼容旧版客户端的 entry.json（标题在父目录）
    for d in (directory, os.path.dirname(os.path.normpath(directory))):
        entry = _load_json(os.path.join(d, 'entry.json'))
        if isinstance(entry, dict):
            title = entry.get('title') or ''
            part = (entry.get('page_data') or {}).get('part') or ''
            if title and part and part != title:
                return safe_filename(f'{title}_{part}')
            if title:
                return safe_filename(title)
    return safe_filename(os.path.basename(os.path.normpath(directory)))


# ---------------------------------------------------------------- 步骤实现

def scan_cache(cache_dir):
    """
    扫描缓存目录，返回 [(源目录, 标题, [m4s文件名...])] 列表。
    只收录含 .m4s 的目录。
    """
    items = []
    for root, _dirs, files in os.walk(cache_dir):
        m4s = [f for f in files if f.lower().endswith('.m4s')]
        if m4s:
            items.append((root, find_title(root), m4s))
    return items


def copy_group(src_dir, files, out_dir, log=_noop):
    """把指定 m4s 文件复制到 out_dir，已存在且大小相同则跳过。"""
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for f in files:
        src = os.path.join(src_dir, f)
        dst = os.path.join(out_dir, f)
        if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
            continue
        shutil.copy2(src, dst)
        n += 1
    # 一并复制标题信息，便于后续步骤取名
    for meta in ('videoInfo.json', 'entry.json'):
        msrc = os.path.join(src_dir, meta)
        if os.path.isfile(msrc):
            shutil.copy2(msrc, os.path.join(out_dir, meta))
    log(f'  已复制 {n} 个文件 -> {out_dir}')
    return n


def strip_header(src_path, dst_path):
    """去除 B 站 m4s 文件开头的 9 个 '0' 字节，写出标准容器文件。"""
    with open(src_path, 'rb') as f:
        data = f.read()
    if data.startswith(b'000000000'):
        data = data[9:]
    elif data[:3] == b'\x00\x00\x00' and data[4:8] != b'ftyp':
        # 少数版本无前缀，保持原样
        pass
    with open(dst_path, 'wb') as f:
        f.write(data)
    return dst_path


def decrypt_dir(directory, pattern, new_ext, log=_noop):
    """
    将 directory 下匹配 pattern 的 .m4s 解密为 new_ext 文件，返回生成的路径列表。
    pattern 为空字符串时匹配全部。
    """
    out = []
    for f in sorted(os.listdir(directory)):
        if not f.lower().endswith('.m4s'):
            continue
        if pattern and pattern not in f:
            continue
        src = os.path.join(directory, f)
        dst = os.path.join(directory, os.path.splitext(f)[0] + new_ext)
        strip_header(src, dst)
        out.append(dst)
    return out


def probe_kinds(path):
    """
    用 ffmpeg 探测文件实际包含的轨道类型，返回集合，如 {'video'}、{'audio'}。
    探测失败返回空集合。传入的应是已去除前导 0 的标准容器文件。
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return set()
    try:
        r = subprocess.run(
            [ffmpeg, '-hide_banner', '-i', path],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            creationflags=_CREATE_NO_WINDOW,
        )
    except OSError:
        return set()
    kinds = set()
    for line in r.stderr.splitlines():
        if 'Stream #' not in line:
            continue
        if ': Video:' in line:
            kinds.add('video')
        elif ': Audio:' in line:
            kinds.add('audio')
    return kinds


def _probe_m4s(directory, filename):
    """把 m4s 去头到临时文件后探测其轨道类型。"""
    src = os.path.join(directory, filename)
    tmp = os.path.join(directory, f'.probe_{filename}.tmp')
    try:
        strip_header(src, tmp)
        return probe_kinds(tmp)
    except OSError:
        return set()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


# 音视频流默认编号：B 站标准清晰度下音频流多为 -30280，视频流多为 -30080 / -100050
DEFAULT_AUDIO = '-30280'
DEFAULT_VIDEO = ('-30080', '-100050')


def _name_has(path, token):
    """文件名（取扩展名前的末段）是否包含某编号，如 '1-1-30280.m4s' 含 '-30280'。"""
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    return token in stem


def _pick_streams(directory, verify=True):
    """
    在目录中区分音频流与视频流 m4s，返回 (音频文件名, 视频文件名)。

    判定策略（按优先级，编号优先于体积，符合 B 站常见命名）：
    1. **音频流**：默认找文件名含 `-30280` 的文件；若找不到，
       则取文件夹内**体积更小**的 m4s（更大的大概率是视频流）。
    2. **视频流**：默认找文件名含 `-30080` 或 `-100050` 的文件；若找不到，
       则取文件夹内**体积更大**的 m4s。
    3. 仅有一个 m4s 时无法凭体积区分，交由 ffmpeg 探测决定其类型。
    4. verify=True 时用 ffmpeg 探测实际轨道类型做最终校正，
       确保选出的流确实含有对应轨道（编号/体积都只是启发式猜测）。
    """
    m4s = [f for f in sorted(os.listdir(directory)) if f.lower().endswith('.m4s')]
    if not m4s:
        return None, None

    if len(m4s) == 1:
        only = m4s[0]
        if verify:
            kinds = _probe_m4s(directory, only)
            if kinds:
                return (only if 'audio' in kinds else None,
                        only if 'video' in kinds else None)
        return only, only

    # 按体积排序，便于回退到大小判断
    by_size = sorted(m4s, key=lambda f: os.path.getsize(os.path.join(directory, f)))
    smallest, largest = by_size[0], by_size[-1]

    # 1) 音频：默认 -30280，找不到取体积最小的
    audio = next((f for f in m4s if _name_has(f, DEFAULT_AUDIO)), None)
    if audio is None:
        audio = smallest

    # 2) 视频：默认 -30080 或 -100050，找不到取体积最大的
    video = next((f for f in m4s if any(_name_has(f, t) for t in DEFAULT_VIDEO)), None)
    if video is None:
        video = largest

    # 防御：音频和视频不能选到同一个文件（除非只有一个流，上面已处理）。
    # 当默认编号都命中同一文件、或回退恰好撞车，优先保证视频取最大、音频取最小。
    if audio == video:
        if audio != largest and largest != video:
            video = largest
        elif audio != smallest and smallest != audio:
            audio = smallest
        else:
            # 实在无法区分，维持体积主从关系：最大为视频，最小为音频
            audio, video = smallest, largest

    if not verify:
        return audio, video

    # 3) 用实际轨道类型校正：编号/体积都只是启发式猜测，探测结果才是事实
    real_audio = real_video = None
    for f in m4s:
        kinds = _probe_m4s(directory, f)
        if not kinds:
            continue
        if 'video' in kinds and real_video is None:
            real_video = f
        elif 'audio' in kinds and 'video' not in kinds and real_audio is None:
            real_audio = f
    if real_audio or real_video:
        return real_audio or audio, real_video or video
    return audio, video


def to_mp3(directory, title, bitrate='192k', log=_noop):
    """将目录内音频流解密并用 ffmpeg 重编码为 <title>.mp3。"""
    audio_m4s, _ = _pick_streams(directory)
    if not audio_m4s:
        log('  未找到音频流，跳过')
        return None
    log(f'  音频流: {audio_m4s}')
    m4a = os.path.join(directory, os.path.splitext(audio_m4s)[0] + '.m4a')
    strip_header(os.path.join(directory, audio_m4s), m4a)
    out_path = os.path.join(directory, safe_filename(title) + '.mp3')
    ok, err = run_ffmpeg(
        ['-y', '-i', m4a, '-vn', '-codec:a', 'libmp3lame', '-b:a', bitrate, out_path],
        log=log,
    )
    if not ok:
        log(f'  ffmpeg 转码失败: {err.strip()[-500:]}')
        return None
    log(f'  已生成 {out_path}')
    return out_path


def to_full_video(directory, title, log=_noop):
    """将目录内音视频流解密并用 ffmpeg 合并为 <title>.mp4（仅封装，不重编码）。"""
    audio_m4s, video_m4s = _pick_streams(directory)
    if not video_m4s:
        log('  未找到视频流，跳过')
        return None
    log(f'  视频流: {video_m4s}' + (f'  音频流: {audio_m4s}' if audio_m4s else ''))
    video_mp4 = os.path.join(directory, os.path.splitext(video_m4s)[0] + '.video.mp4')
    strip_header(os.path.join(directory, video_m4s), video_mp4)

    out_path = os.path.join(directory, safe_filename(title) + '.mp4')
    if audio_m4s and audio_m4s != video_m4s:
        m4a = os.path.join(directory, os.path.splitext(audio_m4s)[0] + '.m4a')
        strip_header(os.path.join(directory, audio_m4s), m4a)
        args = ['-y', '-i', video_mp4, '-i', m4a, '-c', 'copy',
                '-movflags', '+faststart', out_path]
    else:
        log('  未找到独立音频流，仅输出视频')
        args = ['-y', '-i', video_mp4, '-c', 'copy', '-movflags', '+faststart', out_path]

    ok, err = run_ffmpeg(args, log=log)
    if not ok:
        log(f'  ffmpeg 合并失败: {err.strip()[-500:]}')
        return None
    log(f'  已生成 {out_path}')
    return out_path


def cleanup(directory, keep_exts=('.mp3', '.mp4'), log=_noop):
    """删除中间文件，仅保留最终产物。"""
    for f in os.listdir(directory):
        path = os.path.join(directory, f)
        if not os.path.isfile(path):
            continue
        low = f.lower()
        if low.endswith('.m4s') or low.endswith('.m4a') or low.endswith('.video.mp4') \
                or low.endswith('.json'):
            try:
                os.remove(path)
            except OSError:
                pass


# ---------------------------------------------------------------- 主流程

def process(cache_dir, output_dir, mode='audio', bitrate='192k',
            copy_first=True, clean=False, log=_noop, should_stop=None):
    """
    统一处理入口。

    mode: 'audio' 生成 mp3；'video' 生成带音频的完整 mp4。
    copy_first: 先把缓存复制到输出目录再处理（推荐，不动原缓存）。
    clean: 处理完成后删除中间文件。
    should_stop: 可调用对象，返回 True 时中止。
    返回 (成功数, 总数)。
    """
    should_stop = should_stop or (lambda: False)
    if not cache_dir or not os.path.isdir(cache_dir):
        log(f'缓存目录无效: {cache_dir}')
        return 0, 0
    os.makedirs(output_dir, exist_ok=True)

    if not find_ffmpeg():
        log('错误：未找到 ffmpeg，无法进行转码。')
        return 0, 0

    groups = scan_cache(cache_dir)
    total = len(groups)
    if total == 0:
        log('未在该目录下找到任何 .m4s 缓存文件。')
        return 0, 0
    log(f'共发现 {total} 个视频缓存。')

    ok_count = 0
    used_names = {}
    for idx, (src_dir, title, files) in enumerate(groups, 1):
        if should_stop():
            log('已取消。')
            break
        # 同名标题去重
        name = title
        if name in used_names:
            used_names[name] += 1
            name = f'{title}_{used_names[title]}'
        else:
            used_names[name] = 1

        log(f'[{idx}/{total}] {name}')
        work_dir = os.path.join(output_dir, name)
        if copy_first:
            copy_group(src_dir, files, work_dir, log=log)
        else:
            work_dir = src_dir

        try:
            if mode == 'audio':
                res = to_mp3(work_dir, name, bitrate=bitrate, log=log)
            else:
                res = to_full_video(work_dir, name, log=log)
        except Exception as e:  # 单个失败不影响整体
            log(f'  处理异常: {e}')
            res = None

        if res:
            ok_count += 1
            if clean and copy_first:
                cleanup(work_dir, log=log)

    log(f'完成：成功 {ok_count} / {total}')
    return ok_count, total


# ---------------------------------------------------------------- 缓存目录猜测

def guess_cache_dirs():
    """猜测常见的 B 站客户端缓存目录，返回存在的路径列表。"""
    guesses = []
    userprofile = os.environ.get('USERPROFILE', '')
    if userprofile:
        guesses += [
            os.path.join(userprofile, 'Videos', 'bilibili'),
            os.path.join(userprofile, 'Videos', 'Bilibili'),
            os.path.join(userprofile, 'Documents', 'bilibili'),
        ]
    for drive in 'CDEFG':
        guesses.append(f'{drive}:\\bilibili\\download')
        guesses.append(f'{drive}:\\Users\\Public\\Videos\\bilibili')
    return [g for g in guesses if os.path.isdir(g)]
