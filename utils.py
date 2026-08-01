import os
import json


def safe_filename(name, max_len=80):
    """
    将任意标题清洗为跨平台安全的文件夹/文件名：
    去除斜杠、冒号、星号、问号、引号、尖括号、竖线等非法字符，去掉首尾空格与点，限制长度。
    """
    if not name:
        return 'untitled'
    illegal = r'\/:*?"<>|'
    for ch in illegal:
        name = name.replace(ch, '_')
    name = name.strip().strip('.')
    if not name:
        name = 'untitled'
    if len(name) > max_len:
        name = name[:max_len].rstrip('.')
    return name


def find_title(directory):
    """
    读取 directory 下的 videoInfo.json 的 title 字段，返回安全文件夹名。
    找不到 json 或无 title 时，回退为目录名。
    """
    json_path = os.path.join(directory, 'videoInfo.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
            title = info.get('title') or info.get('groupTitle') or ''
            if title:
                return safe_filename(title)
        except (json.JSONDecodeError, OSError):
            pass
    return safe_filename(os.path.basename(os.path.normpath(directory)))


def default_output():
    """返回脚本所在目录下的 output 文件夹绝对路径。"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
