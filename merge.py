import os
import subprocess
import argparse
from utils import find_title, default_output


def merge_directory(directory):
    """
    若 directory 内同时存在视频 mp4（含 -30080）与音频 m4a，
    则合并为 <title>.mp4 到该目录。仅封装不重编码。
    """
    files = os.listdir(directory)
    videos = [f for f in files if f.endswith('.mp4') and '-30080' in f]
    audios = [f for f in files if f.endswith('.m4a')]
    if not videos or not audios:
        return False
    video_path = os.path.join(directory, videos[0])
    audio_path = os.path.join(directory, audios[0])
    out_name = find_title(directory) + '.mp4'
    out_path = os.path.join(directory, out_name)
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-c', 'copy',
        '-movflags', '+faststart',
        out_path,
    ]
    print(f"合并: {video_path} + {audio_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg 失败:\n", result.stderr)
        return False
    print(f"已生成: {out_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='递归将各目录中的 mp4(视频) 与 m4a(音频) 合并为完整 mp4。'
    )
    parser.add_argument(
        '-i', '--input', default=default_output(),
        help='输入根目录，默认项目 output 文件夹'
    )
    args = parser.parse_args()
    count = 0
    for root, dirs, files in os.walk(args.input):
        if merge_directory(root):
            count += 1
    print(f"完成：共合并 {count} 个视频")


if __name__ == '__main__':
    main()
