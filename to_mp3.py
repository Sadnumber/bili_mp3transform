import os
import subprocess
import argparse
from utils import find_title, default_output


def convert_m4a_to_mp3(directory, bitrate='192k'):
    """
    将 directory 内的 m4a 音频用 ffmpeg 重编码为 MP3（libmp3lame），
    输出文件名使用视频标题：<title>.mp3。
    """
    m4as = [f for f in os.listdir(directory) if f.endswith('.m4a')]
    if not m4as:
        return False
    audio_path = os.path.join(directory, m4as[0])
    out_name = find_title(directory) + '.mp3'
    out_path = os.path.join(directory, out_name)
    cmd = [
        'ffmpeg', '-y',
        '-i', audio_path,
        '-codec:a', 'libmp3lame',
        '-b:a', bitrate,
        out_path,
    ]
    print(f"转码: {audio_path} -> {out_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg 失败:\n", result.stderr)
        return False
    print(f"已生成: {out_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='递归将各标题文件夹中的 m4a 音频用 ffmpeg 重编码为 mp3（以标题命名）。'
    )
    parser.add_argument(
        '-i', '--input', default=default_output(),
        help='输入根目录，默认项目 output 文件夹'
    )
    parser.add_argument(
        '-b', '--bitrate', default='192k',
        help='MP3 码率，默认 192k（可选如 128k / 320k）'
    )
    args = parser.parse_args()
    count = 0
    for root, dirs, files in os.walk(args.input):
        if convert_m4a_to_mp3(root, args.bitrate):
            count += 1
    print(f"完成：共生成 {count} 个 mp3")


if __name__ == '__main__':
    main()
