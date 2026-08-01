import os
import argparse
from core import scan_cache, find_title, strip_header, _pick_streams


def process_directory(input_directory, output_directory=None, bitrate='192k'):
    """
    递归遍历 input_directory，将每个缓存目录内的音频流 m4s
    （由 core._pick_streams 识别，默认 -30280）去除前导 9 个 0 后转换为 .m4a。
    默认就地输出到原所在目录；指定 -o 时保留子目录结构输出到该根目录。
    """
    for root, _dirs, _files in os.walk(input_directory):
        items = scan_cache(root)
        if not items:
            continue
        # scan_cache 已按目录聚合，这里只处理恰好等于 root 的条目
        for src_dir, title, _m4s in items:
            if src_dir != root:
                continue
            audio_m4s, _ = _pick_streams(src_dir, verify=False)
            if not audio_m4s:
                print(f"跳过（无音频流）: {src_dir}")
                continue
            out_dir = os.path.join(output_directory, os.path.relpath(root, input_directory)) \
                if output_directory else root
            os.makedirs(out_dir, exist_ok=True)
            src = os.path.join(src_dir, audio_m4s)
            output_filename = os.path.splitext(audio_m4s)[0] + '.m4a'
            output_path = os.path.join(out_dir, output_filename)
            strip_header(src, output_path)
            print(f"已转换 {src} -> {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='将 b站 m4s 音频流（去除前导 9 个 0）批量转换为 m4a。默认就地输出。'
    )
    parser.add_argument(
        '-i', '--input', default=os.path.join(os.path.dirname(__file__), 'output'),
        help='输入目录，默认项目 output 文件夹'
    )
    parser.add_argument(
        '-o', '--output', default=None,
        help='可选输出根目录，保留子目录结构'
    )
    parser.add_argument(
        '-b', '--bitrate', default='192k',
        help='保留参数位（m4a 为原样封装，不使用码率）'
    )
    args = parser.parse_args()
    process_directory(args.input, args.output, args.bitrate)


if __name__ == '__main__':
    main()
