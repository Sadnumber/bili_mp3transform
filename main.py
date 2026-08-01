import os
import shutil
import argparse
from utils import find_title, default_output


def find_and_copy_files(start_dir, target_root, search_pattern):
    """
    遍历 start_dir，对每个包含 .m4s 文件的子目录：
    读取其 videoInfo.json 的 title，在 target_root 下建立同名文件夹，
    将该目录中匹配 search_pattern 的 .m4s 文件复制进去。
    """
    copied = 0
    for root, dirs, files in os.walk(start_dir):
        m4s_files = [f for f in files if f.endswith('.m4s') and search_pattern in f]
        if not m4s_files:
            continue
        title = find_title(root)
        out_dir = os.path.join(target_root, title)
        os.makedirs(out_dir, exist_ok=True)
        for f in m4s_files:
            src = os.path.join(root, f)
            dst = os.path.join(out_dir, f)
            shutil.copy(src, dst)
            print(f"已复制 {src} -> {dst}")
            copied += 1
    return copied


def main():
    parser = argparse.ArgumentParser(
        description='从 b站缓存目录筛选 m4s 文件，按视频标题归类到 output 目录。'
    )
    parser.add_argument(
        '-s', '--source', required=True,
        help='b站缓存起始目录，代码自动遍历其所有子目录'
    )
    parser.add_argument(
        '-t', '--target', default=default_output(),
        help='目标根目录，默认项目内的 output 文件夹'
    )
    parser.add_argument(
        '-p', '--pattern', default='',
        help='文件名匹配模式，默认空=复制所有 .m4s（音频+视频）'
    )
    args = parser.parse_args()
    n = find_and_copy_files(args.source, args.target, args.pattern)
    print(f"完成：共复制 {n} 个文件到 {args.target}")


if __name__ == '__main__':
    main()
