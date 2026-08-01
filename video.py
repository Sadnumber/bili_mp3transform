import os
import argparse
from core import scan_cache, find_title, strip_header, _pick_streams, run_ffmpeg, safe_filename


def process_directory(input_directory, output_directory=None, clean=False):
    """
    递归遍历 input_directory，将每个缓存目录内的音视频流 m4s
    （由 core._pick_streams 识别）解密并用 ffmpeg 合并为带音频的完整 .mp4。
    默认就地输出到原所在目录；指定 -o 时保留子目录结构输出到该根目录。
    """
    for root, _dirs, _files in os.walk(input_directory):
        items = scan_cache(root)
        if not items:
            continue
        for src_dir, title, _m4s in items:
            if src_dir != root:
                continue
            audio_m4s, video_m4s = _pick_streams(src_dir, verify=True)
            if not video_m4s:
                print(f"跳过（无视频流）: {src_dir}")
                continue

            out_dir = os.path.join(output_directory, os.path.relpath(root, input_directory)) \
                if output_directory else root
            os.makedirs(out_dir, exist_ok=True)
            print(f"处理: {src_dir}  视频流={video_m4s}  音频流={audio_m4s or '无'}")

            video_mp4 = os.path.join(out_dir, os.path.splitext(video_m4s)[0] + '.video.mp4')
            strip_header(os.path.join(src_dir, video_m4s), video_mp4)

            out_path = os.path.join(out_dir, safe_filename(title) + '.mp4')
            if audio_m4s and audio_m4s != video_m4s:
                m4a = os.path.join(out_dir, os.path.splitext(audio_m4s)[0] + '.m4a')
                strip_header(os.path.join(src_dir, audio_m4s), m4a)
                args = ['-y', '-i', video_mp4, '-i', m4a, '-c', 'copy',
                        '-movflags', '+faststart', out_path]
            else:
                print('  未找到独立音频流，仅输出视频')
                args = ['-y', '-i', video_mp4, '-c', 'copy', '-movflags', '+faststart', out_path]

            ok, err = run_ffmpeg(args)
            if not ok:
                print(f"  合并失败: {err.strip()[-500:]}")
                continue
            print(f"已生成 {out_path}")
            if clean:
                for tmp in (video_mp4, m4a if (audio_m4s and audio_m4s != video_m4s) else None):
                    if tmp and os.path.isfile(tmp):
                        os.remove(tmp)


def main():
    parser = argparse.ArgumentParser(
        description='将 b站 m4s 音视频流合并为带音频的完整 mp4。默认就地输出。'
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
        '--clean', action='store_true',
        help='转换完成后删除中间文件（.m4s/.m4a/.video.mp4）'
    )
    args = parser.parse_args()
    process_directory(args.input, args.output, clean=args.clean)


if __name__ == '__main__':
    main()
