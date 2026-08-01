import os
import argparse
from utils import default_output


def remove_leading_zeros(file_path, output_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    if data.startswith(b'000000000'):
        data = data[9:]
    with open(output_path, 'wb') as f:
        f.write(data)


def process_directory(input_directory, output_directory=None, pattern='-30080'):
    """
    递归遍历 input_directory，将匹配 pattern 的 .m4s（默认视频流 -30080）
    去除前导 9 个 0 后转换为 .mp4。
    默认就地输出到原所在目录；指定 -o 时保留子目录结构输出到该根目录。
    """
    for root, dirs, files in os.walk(input_directory):
        for filename in files:
            if not filename.endswith('.m4s') or pattern not in filename:
                continue
            file_path = os.path.join(root, filename)
            if output_directory:
                rel = os.path.relpath(root, input_directory)
                out_dir = os.path.join(output_directory, rel)
                os.makedirs(out_dir, exist_ok=True)
            else:
                out_dir = root
            output_filename = filename.replace('.m4s', '.mp4')
            output_path = os.path.join(out_dir, output_filename)
            remove_leading_zeros(file_path, output_path)
            print(f"已转换 {file_path} -> {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='将 b站 m4s 视频流（去除前导 9 个 0）批量转换为 mp4。默认就地输出。'
    )
    parser.add_argument(
        '-i', '--input', default=default_output(),
        help='输入目录，默认项目 output 文件夹'
    )
    parser.add_argument(
        '-o', '--output', default=None,
        help='可选输出根目录，保留子目录结构'
    )
    parser.add_argument(
        '-p', '--pattern', default='-30080',
        help='文件名匹配模式，默认 "-30080"（视频流）'
    )
    args = parser.parse_args()
    process_directory(args.input, args.output, args.pattern)


if __name__ == '__main__':
    main()
