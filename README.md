# bili_mp3transform
将 b站客户端下载的 m4s 文件（音频流/视频流）解密并转换为可播放的 m4a / mp4，最终合并为完整 mp4 视频。

## 工作原理
- b站的“加密”很简单：在 m4s 文件开头放入 9 个 `0` 字节，删除即可还原为标准 MP4 容器。
- 音频流文件名含 `-30280`，解密后为 AAC 编码（用 `.m4a` 后缀更准确）。
- 视频流文件名含 `-30080`，解密后为 H.264 编码（`.mp4`）。
- 用 `ffmpeg` 将视频 mp4 与音频 m4a 封装合并，得到带声音的完整 mp4（仅封装，不重新编码，无损且快速）。

## 文件说明
- `utils.py`：公共工具。读取视频文件夹下 `videoInfo.json` 的 `title` 作为安全文件夹名；提供默认 output 路径。
- `main.py`：从 b站缓存目录递归筛选 `.m4s` 文件，按每个视频的 `title` 在 `output/` 下建立同名文件夹，并将该视频的 m4s 复制进去。
- `test.py`：将 `output/` 中的音频 m4s（`-30280`）解密转为 `.m4a`。默认就地输出到原文件夹。
- `video.py`：将视频 m4s（`-30080`）解密转为 `.mp4`。默认就地输出到原文件夹。
- `merge.py`：递归扫描 `output/`，将每个标题文件夹内的视频 mp4 与音频 m4a 合并为 `<标题>.mp4`。
- `to_mp3.py`：将每个标题文件夹内的 `.m4a` 音频用 `ffmpeg` 真正重编码为 MP3（libmp3lame），输出为 `<标题>.mp3`。

## 命令行用法
所有脚本的目标目录默认值均为项目内的 `output/` 文件夹，因此可以几乎零参数运行。

### 1. main.py 提取并归类
```bash
python main.py -s /path/to/bilibili_cache
```
- `-s / --source`：b站缓存起始目录（必填）
- `-t / --target`：目标根目录，默认项目内 `output/`
- `-p / --pattern`：文件名匹配模式，默认空=复制所有 `.m4s`（音频+视频）

### 2. test.py 转音频 m4a
```bash
python test.py            # 默认处理 output/ 内所有音频流
```
- `-i / --input`：输入目录，默认 `output/`
- `-o / --output`：可选输出根目录（保留子目录结构），默认就地输出
- `-p / --pattern`：默认 `-30280`

### 3. video.py 转视频 mp4
```bash
python video.py           # 默认处理 output/ 内所有视频流
```
- 参数同 test.py，默认 pattern `-30080`

### 4. merge.py 合并为完整 mp4
```bash
python merge.py           # 默认递归处理 output/ 内各标题文件夹
```
- `-i / --input`：输入根目录，默认 `output/`

### 5. to_mp3.py 将 m4a 重编码为 mp3
```bash
python to_mp3.py          # 默认递归处理 output/ 内各标题文件夹
```
- `-i / --input`：输入根目录，默认 `output/`
- `-b / --bitrate`：MP3 码率，默认 `192k`（可选 `128k` / `320k`）

## 完整示例（使用默认 output 目录）
```bash
python main.py -s /Users/ruanyancheng/Movies/bilibili
python test.py
python video.py
python to_mp3.py
python merge.py
```
执行后 `output/《原神》7.0版本PV：「无神怜爱的雪国」/` 下会包含：
- `*.m4s`（原始，可手动删除）
- `*-30280.m4a`（音频，AAC）
- `*-30080.mp4`（视频）
- `《原神》7.0版本PV：「无神怜爱的雪国」.mp3`（音频，MP3 编码）
- `《原神》7.0版本PV：「无神怜爱的雪国」.mp4`（最终合并视频，可直接播放）

> 合并步骤依赖 `ffmpeg`，请先通过 `brew install ffmpeg`（macOS）或对应包管理器安装。
