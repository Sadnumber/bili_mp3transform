"""
B站缓存转换器 - 图形界面

首次使用设置 B 站缓存目录（必选）与输出目录、码率等（可选），
之后直接点击「转换为音频」或「转换为完整视频」即可。
"""
import os
import sys
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import core

APP_NAME = 'BiliCacheConverter'
APP_TITLE = 'B站缓存转换器'


def config_path():
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'config.json')


def load_config():
    default = {
        'cache_dir': '',
        'output_dir': os.path.join(
            os.environ.get('USERPROFILE', os.path.expanduser('~')),
            'Desktop', 'B站转换输出'),
        'bitrate': '192k',
        'clean': True,
        'open_when_done': True,
    }
    try:
        with open(config_path(), 'r', encoding='utf-8') as f:
            default.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    if not default['cache_dir']:
        guesses = core.guess_cache_dirs()
        if guesses:
            default['cache_dir'] = guesses[0]
    return default


def save_config(cfg):
    try:
        with open(config_path(), 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry('760x560')
        self.minsize(680, 480)
        try:
            self.call('tk', 'scaling', 1.3)
        except tk.TclError:
            pass

        self.cfg = load_config()
        self.log_queue = queue.Queue()
        self.worker = None
        self.stop_flag = False

        self._build_ui()
        self.after(100, self._drain_log)
        self.protocol('WM_DELETE_WINDOW', self._on_close)

        if not core.find_ffmpeg():
            self._log('警告：未检测到 ffmpeg，转换功能不可用。')
        else:
            self._log(f'ffmpeg: {core.find_ffmpeg()}')
        if not self.cfg['cache_dir']:
            self._log('请先设置 B站缓存目录（客户端「设置-下载设置」中可查看）。')

    # ------------------------------------------------------------ UI
    def _build_ui(self):
        pad = {'padx': 8, 'pady': 6}
        style = ttk.Style(self)
        try:
            style.theme_use('vista')
        except tk.TclError:
            pass
        style.configure('Big.TButton', font=('Microsoft YaHei UI', 11, 'bold'), padding=10)

        frm = ttk.LabelFrame(self, text='设置')
        frm.pack(fill='x', **pad)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text='B站缓存目录 *').grid(row=0, column=0, sticky='w', padx=8, pady=6)
        self.var_cache = tk.StringVar(value=self.cfg['cache_dir'])
        ttk.Entry(frm, textvariable=self.var_cache).grid(row=0, column=1, sticky='ew', pady=6)
        ttk.Button(frm, text='浏览…', command=self._pick_cache).grid(row=0, column=2, padx=8)

        ttk.Label(frm, text='输出目录').grid(row=1, column=0, sticky='w', padx=8, pady=6)
        self.var_out = tk.StringVar(value=self.cfg['output_dir'])
        ttk.Entry(frm, textvariable=self.var_out).grid(row=1, column=1, sticky='ew', pady=6)
        ttk.Button(frm, text='浏览…', command=self._pick_out).grid(row=1, column=2, padx=8)

        opt = ttk.Frame(frm)
        opt.grid(row=2, column=0, columnspan=3, sticky='w', padx=8, pady=4)
        ttk.Label(opt, text='MP3 码率').pack(side='left')
        self.var_bitrate = tk.StringVar(value=self.cfg['bitrate'])
        ttk.Combobox(opt, textvariable=self.var_bitrate, width=8, state='readonly',
                     values=['128k', '192k', '256k', '320k']).pack(side='left', padx=(6, 20))
        self.var_clean = tk.BooleanVar(value=self.cfg['clean'])
        ttk.Checkbutton(opt, text='完成后删除中间文件', variable=self.var_clean).pack(side='left', padx=(0, 20))
        self.var_open = tk.BooleanVar(value=self.cfg['open_when_done'])
        ttk.Checkbutton(opt, text='完成后打开输出目录', variable=self.var_open).pack(side='left')

        btns = ttk.Frame(self)
        btns.pack(fill='x', **pad)
        self.btn_audio = ttk.Button(btns, text='转换为音频 (MP3)', style='Big.TButton',
                                    command=lambda: self._start('audio'))
        self.btn_audio.pack(side='left', expand=True, fill='x', padx=(0, 6))
        self.btn_video = ttk.Button(btns, text='转换为完整视频 (MP4)', style='Big.TButton',
                                    command=lambda: self._start('video'))
        self.btn_video.pack(side='left', expand=True, fill='x', padx=(6, 6))
        self.btn_stop = ttk.Button(btns, text='停止', command=self._stop, state='disabled')
        self.btn_stop.pack(side='left', padx=(6, 0))

        self.progress = ttk.Progressbar(self, mode='determinate')
        self.progress.pack(fill='x', padx=8)

        logfrm = ttk.LabelFrame(self, text='日志')
        logfrm.pack(fill='both', expand=True, **pad)
        self.txt = tk.Text(logfrm, wrap='word', height=14, state='disabled',
                           font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4')
        sb = ttk.Scrollbar(logfrm, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.txt.pack(side='left', fill='both', expand=True)

        self.status = tk.StringVar(value='就绪')
        ttk.Label(self, textvariable=self.status, anchor='w').pack(fill='x', padx=10, pady=(0, 6))

    # ------------------------------------------------------------ 事件
    def _pick_cache(self):
        d = filedialog.askdirectory(title='选择 B站缓存目录',
                                    initialdir=self.var_cache.get() or os.path.expanduser('~'))
        if d:
            self.var_cache.set(os.path.normpath(d))

    def _pick_out(self):
        d = filedialog.askdirectory(title='选择输出目录',
                                    initialdir=self.var_out.get() or os.path.expanduser('~'))
        if d:
            self.var_out.set(os.path.normpath(d))

    def _collect_cfg(self):
        self.cfg.update({
            'cache_dir': self.var_cache.get().strip(),
            'output_dir': self.var_out.get().strip(),
            'bitrate': self.var_bitrate.get(),
            'clean': bool(self.var_clean.get()),
            'open_when_done': bool(self.var_open.get()),
        })
        save_config(self.cfg)
        return self.cfg

    def _start(self, mode):
        if self.worker and self.worker.is_alive():
            return
        cfg = self._collect_cfg()
        if not cfg['cache_dir'] or not os.path.isdir(cfg['cache_dir']):
            messagebox.showwarning(APP_TITLE, '请先选择有效的 B站缓存目录。')
            return
        if not cfg['output_dir']:
            messagebox.showwarning(APP_TITLE, '请先选择输出目录。')
            return
        if not core.find_ffmpeg():
            messagebox.showerror(APP_TITLE, '未找到 ffmpeg，无法转换。')
            return

        self.stop_flag = False
        self._set_running(True)
        self.progress.configure(mode='indeterminate')
        self.progress.start(12)
        self.status.set('转换为音频中…' if mode == 'audio' else '合并完整视频中…')
        self._log('=' * 50)

        def run():
            try:
                core.process(
                    cache_dir=cfg['cache_dir'],
                    output_dir=cfg['output_dir'],
                    mode=mode,
                    bitrate=cfg['bitrate'],
                    copy_first=True,
                    clean=cfg['clean'],
                    log=self._log,
                    should_stop=lambda: self.stop_flag,
                )
            except Exception as e:
                self._log(f'发生错误: {e}')
            finally:
                self.log_queue.put(('__done__', cfg))

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def _stop(self):
        self.stop_flag = True
        self.status.set('正在停止…')

    def _set_running(self, running):
        state = 'disabled' if running else 'normal'
        self.btn_audio.configure(state=state)
        self.btn_video.configure(state=state)
        self.btn_stop.configure(state='normal' if running else 'disabled')

    def _log(self, msg):
        self.log_queue.put(('log', str(msg)))

    def _drain_log(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == '__done__':
                    self._on_finished(payload)
                else:
                    self.txt.configure(state='normal')
                    self.txt.insert('end', payload + '\n')
                    self.txt.see('end')
                    self.txt.configure(state='disabled')
        except queue.Empty:
            pass
        self.after(100, self._drain_log)

    def _on_finished(self, cfg):
        self.progress.stop()
        self.progress.configure(mode='determinate', value=0)
        self._set_running(False)
        self.status.set('已完成')
        if cfg.get('open_when_done') and os.path.isdir(cfg['output_dir']):
            try:
                os.startfile(cfg['output_dir'])
            except OSError:
                pass

    def _on_close(self):
        self._collect_cfg()
        if self.worker and self.worker.is_alive():
            if not messagebox.askokcancel(APP_TITLE, '任务仍在进行，确定要退出吗？'):
                return
            self.stop_flag = True
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
