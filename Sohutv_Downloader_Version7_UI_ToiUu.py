import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import requests
from bs4 import BeautifulSoup
import re
import subprocess
import os
import webbrowser
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
import time

# Các hàm helper không thay đổi
def extract_playlist_from_video_page(html):
    soup = BeautifulSoup(html, "html.parser"); playlist = []; seen_urls = set()
    ul = soup.find('ul', id='menu_box_broadlist')
    if ul:
        for li in ul.find_all('li', class_='broadlist-video-card'):
            data_url = li.get('data-url'); title = li.get('data-title', '').strip()
            if data_url:
                if data_url.startswith('//'): full_url = 'https:' + data_url
                elif data_url.startswith('/'): full_url = 'https://tv.sohu.com' + data_url
                else: full_url = data_url
                if full_url not in seen_urls: playlist.append({'title': title or full_url, 'url': full_url}); seen_urls.add(full_url)
    return playlist

def get_video_info(video_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        resp = requests.get(video_url, headers=headers, timeout=10); resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser"); title_tag = soup.find("title")
        title = title_tag.string.strip() if title_tag and title_tag.string else video_url
    except Exception as e: print(f"Lỗi khi lấy info video: {e}"); title = video_url
    return (title, video_url)

class SohutvDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sohu Multi Video Downloader - By Tony Nguyen (vFinal-Checkbox)")
        self.links, self.links_set = [], set()
        self.save_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        self.downloading, self.stop_download = False, False
        self.driver, self._drag_start_item = None, None
        self.selenium_busy = False
        
        # NÂNG CẤP: Thêm biến cho checkbox
        self.merge_var = tk.BooleanVar(value=False)
        
        self.create_widgets()
        self.update_count_label()
        
        self.setup_status_bar()

    def setup_status_bar(self):
        # ... (Hàm này không thay đổi)
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 2))
        self.text_status_var = tk.StringVar(); self.text_status_var.set("Sẵn sàng.")
        self.text_status_label = ttk.Label(self.status_frame, textvariable=self.text_status_var, anchor="w")
        
        self.progress_container = ttk.Frame(self.status_frame)
        self.progress_title_var = tk.StringVar()
        self.progress_title_label = ttk.Label(self.progress_container, textvariable=self.progress_title_var, anchor="w")
        self.progress_title_label.pack(side="left", padx=(0, 5))
        self.progress_bar = ttk.Progressbar(self.progress_container, orient='horizontal', mode='determinate')
        self.progress_bar.pack(side="left", fill="x", expand=True)
        self.progress_details_var = tk.StringVar()
        self.progress_details_label = ttk.Label(self.progress_container, textvariable=self.progress_details_var, anchor="w")
        self.progress_details_label.pack(side="left", padx=(5, 0))
        
        self.show_text_status("Sẵn sàng.")

    def show_text_status(self, text):
        # ... (Hàm này không thay đổi)
        def update_ui():
            if self.progress_container.winfo_viewable(): self.progress_container.pack_forget()
            if not self.text_status_label.winfo_viewable(): self.text_status_label.pack(side="left", fill="x", expand=True)
            self.text_status_var.set(text)
        self.root.after(0, update_ui)

    def show_progress_status(self, title, percent, details):
        # ... (Hàm này không thay đổi)
        def update_ui(p_title, p_percent, p_details):
            if self.text_status_label.winfo_viewable(): self.text_status_label.pack_forget()
            if not self.progress_container.winfo_viewable(): self.progress_container.pack(side="left", fill="x", expand=True)
            self.progress_title_var.set(f"Tải: {p_title[:30]}...")
            self.progress_bar['value'] = p_percent
            self.progress_details_var.set(p_details)
        self.root.after(0, update_ui, title, percent, details)

    def start_driver(self, url):
        # ... (Hàm này không thay đổi)
        if self.driver is None:
            chromedriver_autoinstaller.install()
            chrome_options = Options(); chrome_options.add_argument("--headless=new"); chrome_options.add_argument("--disable-gpu"); chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--window-size=1920,1080"); chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--lang=zh-CN"); chrome_options.add_argument("log-level=3"); chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.get(url)

    def get_full_playlist_realtime(self):
        # ... (Hàm này không thay đổi)
        if self.selenium_busy: messagebox.showinfo("Thông báo", "Đang có tác vụ khác chạy..."); return
        playlist_url = self.link_entry.get().strip()
        if not playlist_url: messagebox.showinfo("Thông báo", "Vui lòng nhập link playlist."); return
        self.delete_all(confirm=False)

        def task():
            self.selenium_busy = True
            try:
                self.show_text_status("Đang khởi động trình duyệt..."); self.start_driver(playlist_url)
                wait = WebDriverWait(self.driver, 20); self.show_text_status("Trang đã tải, đang chờ playlist...")
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ul#menu_box_broadlist li.broadlist-video-card')))
                playlist_ul = self.driver.find_element(By.ID, 'menu_box_broadlist')
                last_count = retries = 0; max_retries = 3; sleep_time = 1.2
                while retries < max_retries:
                    self.show_text_status(f"Đang cuộn và tìm video... (Thử lại: {retries}/{max_retries})")
                    current_playlist = extract_playlist_from_video_page(self.driver.page_source)
                    new_videos_found = False
                    for item in current_playlist:
                        if item['url'] not in self.links_set:
                            new_videos_found = True
                            self.links_set.add(item['url']); self.root.after(0, self.add_video_to_tree, item['title'], item['url'])
                    if new_videos_found: last_count = len(self.links_set); retries = 0
                    else: retries += 1
                    video_cards = playlist_ul.find_elements(By.CSS_SELECTOR, "li.broadlist-video-card")
                    if video_cards: self.driver.execute_script("arguments[0].scrollIntoView();", video_cards[-1])
                    time.sleep(sleep_time)
                self.show_text_status(f"Hoàn tất! Đã tìm thấy tất cả {len(self.links_set)} video.")
            except Exception as e:
                self.show_text_status(f"Lỗi: {e}"); messagebox.showerror("Lỗi", f"Đã xảy ra lỗi khi lấy playlist:\n{e}")
            finally: self.selenium_busy = False
        threading.Thread(target=task, daemon=True).start()
    
    def add_video_to_tree(self, title, url):
        # ... (Hàm này không thay đổi)
        if not self.root.winfo_exists(): return
        idx = len(self.links)
        self.links.append((title, url))
        self.tree.insert("", "end", iid=str(idx), values=(title, url))
        self.tree.yview_moveto(1); self.update_count_label()

    def create_widgets(self):
        # ... (Code tạo widget không thay đổi nhiều)
        self.root.grid_rowconfigure(0, weight=1); self.root.grid_columnconfigure(0, weight=1)
        frm = ttk.Frame(self.root, padding=10); frm.grid(row=0, column=0, sticky="nsew")
        input_frame = ttk.Frame(frm); input_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10)); input_frame.columnconfigure(0, weight=1)
        ttk.Label(input_frame, text="Nhập link video hoặc playlist Sohu:").grid(row=0, column=0, columnspan=2, sticky='w')
        self.link_entry = tk.Entry(input_frame, width=70); self.link_entry.grid(row=1, column=0, sticky="ew")
        self.get_playlist_btn = ttk.Button(input_frame, text="Lấy playlist", command=self.get_full_playlist_realtime); self.get_playlist_btn.grid(row=1, column=1, padx=5)
        
        tree_frame = ttk.Frame(frm); tree_frame.grid(row=1, column=0, columnspan=2, sticky="nsew"); tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1); frm.grid_rowconfigure(1, weight=1); frm.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=("title", "url"), show="headings", selectmode="extended")
        self.tree.heading("title", text="Tiêu đề"); self.tree.heading("url", text="URL"); self.tree.column("title", width=300, anchor="w"); self.tree.column("url", width=400, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=scrollbar.set); scrollbar.grid(row=0, column=1, sticky='ns')

        bottom_frame = ttk.Frame(frm); bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        self.download_btn = ttk.Button(bottom_frame, text="Tải video đã chọn", command=self.download_selected); self.download_btn.pack(side=tk.LEFT, pady=(10,0))
        ttk.Button(bottom_frame, text="Chọn thư mục lưu", command=self.choose_dir).pack(side=tk.LEFT, padx=10, pady=(10,0))
        self.dir_label = ttk.Label(bottom_frame, text=f"Lưu về: {self.save_dir}"); self.dir_label.pack(side=tk.LEFT, padx=10, pady=(10,0))
        
        # NÂNG CẤP: Thêm checkbox "Ghép file"
        self.merge_checkbox = ttk.Checkbutton(bottom_frame, text="Ghép file", variable=self.merge_var, state="disabled")
        self.merge_checkbox.pack(side=tk.LEFT, padx=10, pady=(10,0))

        self.count_label = ttk.Label(bottom_frame, text=""); self.count_label.pack(side=tk.LEFT, padx=10, pady=(10,0))
        
        self.setup_menus_and_bindings()

    def setup_menus_and_bindings(self):
        # ... (Hàm này không thay đổi)
        self.entry_menu = tk.Menu(self.root, tearoff=0); self.entry_menu.add_command(label="Dán", command=self.paste_to_entry)
        self.link_entry.bind("<Button-3>", lambda e: self.entry_menu.tk_popup(e.x_root, e.y_root))
        self.tree_menu = tk.Menu(self.root, tearoff=0); self.tree_menu.add_command(label="Copy URL đã chọn", command=self.copy_selected)
        self.tree_menu.add_command(label="Dán và Thêm 1 Video", command=self.paste_and_add_single_video); self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Chọn tất cả", command=self.select_all); self.tree_menu.add_command(label="Bỏ chọn tất cả", command=self.deselect_all)
        self.tree_menu.add_separator(); self.tree_menu.add_command(label="Xóa mục đã chọn", command=self.delete_selected)
        self.tree_menu.add_command(label="Xóa tất cả", command=lambda: self.delete_all(confirm=True))
        self.tree.bind("<Button-3>", lambda e: self.tree_menu.tk_popup(e.x_root, e.y_root))
        self.tree.bind("<Double-1>", self.open_video_in_browser); self.tree.bind("<Button-1>", self.on_tree_button1_press)
        self.tree.bind("<B1-Motion>", self.on_tree_drag); self.tree.bind("<ButtonRelease-1>", self.on_tree_button1_release)
        self.tree.bind("<<TreeviewSelect>>", self.update_count_label)
    
    def paste_and_add_single_video(self):
        # ... (Hàm này không thay đổi)
        try:
            url = self.root.clipboard_get().strip()
            if not url or not url.startswith("http"): return
            if url in self.links_set: messagebox.showinfo("Thông báo", "Link này đã có trong danh sách."); return
            def task():
                self.show_text_status(f"Đang lấy thông tin cho link: {url[:50]}..."); title, video_url = get_video_info(url)
                if video_url not in self.links_set:
                    self.links_set.add(video_url); self.root.after(0, self.add_video_to_tree, title, video_url)
                    self.show_text_status("Đã thêm video thành công.")
                else: self.show_text_status("Link đã tồn tại.")
            threading.Thread(target=task, daemon=True).start()
        except tk.TclError: pass
        
    def download_selected(self):
        # ... (Hàm này không thay đổi)
        if self.downloading:
            self.stop_download = True; self.show_text_status("Đang yêu cầu dừng tải..."); self.download_btn.config(state="disabled")
            return
        selected_iids = self.tree.selection()
        if not selected_iids: messagebox.showwarning("Chọn video", "Vui lòng chọn ít nhất một video để tải."); return
        to_download = [self.links[int(i)] for i in selected_iids]
        self.downloading = True; self.stop_download = False; self.download_btn.config(text="Dừng tải")

        def task():
            downloaded_files = []
            for title, url in to_download:
                if self.stop_download: break
                safe_title = re.sub(r'[\\/*?:"<>|]', "", title); output_template = f"{safe_title}.mp4"
                progress_regex = re.compile(r"\[download\]\s+(?P<percent>[\d\.]+)%\s+of\s+~?\s*(?P<total>[\d\.]+\s*\w+)")
                try:
                    cmd = ['yt-dlp', '-P', self.save_dir, '-o', output_template, '--progress', '--no-warnings', '--force-overwrites', url]
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW)
                    line_buffer = b''
                    while True:
                        if self.stop_download: process.terminate(); break
                        char = process.stdout.read(1)
                        if not char and process.poll() is not None: break
                        if char:
                            line_buffer += char
                            if char in (b'\r', b'\n'):
                                line = line_buffer.decode('utf-8', errors='replace').strip(); line_buffer = b''
                                match = progress_regex.search(line)
                                if match:
                                    percent = float(match.group('percent')); total_str = match.group('total').strip().replace("~","")
                                    total_val_match = re.search(r'([\d\.]+)', total_str); unit_match = re.search(r'([a-zA-Z]+)', total_str)
                                    if total_val_match and unit_match:
                                        total_val = float(total_val_match.group(1)); unit = unit_match.group(1)
                                        current_val = (total_val * percent) / 100.0
                                        details_text = f"{percent:.1f}% ({current_val:.2f}{unit}/{total_str})"
                                    else: details_text = f"{percent:.1f}%"
                                    self.show_progress_status(safe_title, percent, details_text)
                    process.wait()
                    if process.returncode != 0 and not self.stop_download: raise subprocess.CalledProcessError(process.returncode, cmd, stderr=process.stderr.read().decode('utf-8', errors='replace'))
                    if not self.stop_download:
                        full_path = os.path.join(self.save_dir, output_template)
                        if os.path.exists(full_path): downloaded_files.append(full_path)
                except subprocess.CalledProcessError as e: self.show_text_status(f"Lỗi tải {title}."); print(f"Lỗi yt-dlp:\n{e.stderr}")
                except Exception as e: self.show_text_status(f"Lỗi không xác định khi tải {title}."); print(f"Lỗi tải: {e}")
            self.downloading = False
            self.root.after(0, self.on_download_finish, downloaded_files)
        threading.Thread(target=task, daemon=True).start()

    # NÂNG CẤP: Xử lý logic ghép file dựa trên checkbox
    def on_download_finish(self, downloaded_files):
        self.download_btn.config(text="Tải video đã chọn", state="normal")
        status_msg = "Quá trình tải đã được người dùng dừng lại." if self.stop_download else "Hoàn tất tải các video đã chọn."
        self.show_text_status(status_msg); self.stop_download = False
        
        if len(downloaded_files) >= 2:
            # Nếu checkbox được tick, tự động ghép. Nếu không, hỏi người dùng.
            if self.merge_var.get():
                self.merge_videos(downloaded_files)
            else:
                if messagebox.askyesno("Ghép video", f"Đã tải xong {len(downloaded_files)} files. Bạn có muốn ghép chúng thành 1 file không?"):
                    self.merge_videos(downloaded_files)

    # NÂNG CẤP: Cập nhật trạng thái của checkbox
    def update_count_label(self, event=None):
        selected_count = len(self.tree.selection())
        self.count_label.config(text=f"Đã chọn: {selected_count} / Tổng số: {len(self.links)}")
        
        if selected_count >= 2:
            self.merge_checkbox.config(state="normal")
        else:
            self.merge_checkbox.config(state="disabled")
            self.merge_var.set(False) # Tự động bỏ tick nếu chọn dưới 2 video

    # ... (Các hàm còn lại không thay đổi)
    def on_tree_button1_press(self, event): self._drag_start_item = self.tree.identify_row(event.y)
    def on_tree_drag(self, event):
        if not self._drag_start_item: return
        end_item = self.tree.identify_row(event.y)
        if not end_item: return
        start_index = self.tree.index(self._drag_start_item); end_index = self.tree.index(end_item)
        self.deselect_all(update_label=False)
        all_items = self.tree.get_children('');
        if start_index > end_index: start_index, end_index = end_index, start_index
        for i in range(start_index, end_index + 1): self.tree.selection_add(all_items[i])
        self.update_count_label()
    def on_tree_button1_release(self, event): self._drag_start_item = None
    def delete_all(self, confirm=True):
        if not self.links: return
        if not confirm or messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa tất cả?"):
            self.tree.delete(*self.tree.get_children()); self.links.clear(); self.links_set.clear(); self.update_count_label()
    def delete_selected(self):
        selected_iids = self.tree.selection()
        if not selected_iids: return
        selected_urls = {self.tree.item(iid, "values")[1] for iid in selected_iids}
        self.links_set -= selected_urls; self.links = [item for item in self.links if item[1] not in selected_urls]
        for iid in selected_iids: self.tree.delete(iid)
        for i, iid in enumerate(self.tree.get_children()): self.tree.item(iid, iid=str(i))
        self.update_count_label()
    def select_all(self): self.tree.selection_add(*self.tree.get_children()); self.update_count_label()
    def deselect_all(self, update_label=True):
        if self.tree.selection(): self.tree.selection_remove(self.tree.selection())
        if update_label: self.update_count_label()
    def paste_to_entry(self):
        try: text = self.root.clipboard_get(); self.link_entry.delete(0, tk.END); self.link_entry.insert(0, text)
        except tk.TclError: pass
    def copy_selected(self):
        selected_iids = self.tree.selection();
        if not selected_iids: return
        urls = [self.tree.item(i, "values")[1] for i in selected_iids]; self.root.clipboard_clear(); self.root.clipboard_append('\n'.join(urls))
    def open_video_in_browser(self, event):
        item_id = self.tree.identify_row(event.y);
        if item_id: webbrowser.open(self.tree.item(item_id, "values")[1])
    def choose_dir(self):
        dir_selected = filedialog.askdirectory();
        if dir_selected: self.save_dir = dir_selected; self.dir_label.config(text=f"Lưu về: {self.save_dir}")
    def merge_videos(self, file_list):
        if len(file_list) < 2: return
        def sort_key(filepath): match = re.search(r'第(\d+)集', os.path.basename(filepath)); return int(match.group(1)) if match else 9999
        file_list.sort(key=sort_key)
        first_filename = os.path.basename(file_list[0]); last_filename = os.path.basename(file_list[-1])
        base_name_match = re.match(r'(.+?)\s*第\d+集', first_filename)
        base_name = base_name_match.group(1).strip() if base_name_match else "Playlist"
        start_ep_match = re.search(r'第(\d+)集', first_filename); end_ep_match = re.search(r'第(\d+)集', last_filename)
        ep_range = ""
        if start_ep_match and end_ep_match:
            start_num = start_ep_match.group(1); end_num = end_ep_match.group(1)
            ep_range = f" {start_num}-{end_num}"
        now_str = time.strftime("%Y%m%d_%H%M%S")
        output_file_name = f"Sohu_Full_{base_name}{ep_range}_{now_str}.mp4"
        output_file_path = os.path.join(self.save_dir, output_file_name)
        concat_file = os.path.join(self.save_dir, "temp_concat_list.txt")
        try:
            with open(concat_file, "w", encoding="utf-8") as f:
                for file_path in file_list: f.write(f"file '{os.path.basename(file_path)}'\n")
            self.show_text_status(f"Đang ghép {len(file_list)} video...")
            subprocess.run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', os.path.basename(concat_file), '-c', 'copy', os.path.basename(output_file_path)],
                check=True, cwd=self.save_dir, capture_output=True, text=True, encoding='utf-8')
            self.show_text_status(f"Đã ghép xong! File được lưu tại: {output_file_name}")
            messagebox.showinfo("Thành công", f"Đã ghép xong thành công!\nFile: {output_file_name}")
        except subprocess.CalledProcessError as e: messagebox.showerror("Lỗi ghép video", f"Lỗi khi ghép video: {e.stderr}")
        except Exception as e: messagebox.showerror("Lỗi ghép video", f"Lỗi không xác định: {e}")
        finally:
            if os.path.exists(concat_file): os.remove(concat_file)
    def quit_driver(self):
        if self.driver:
            try: self.driver.quit()
            except Exception: pass
            self.driver = None

if __name__ == "__main__":
    root = tk.Tk()
    app = SohutvDownloaderApp(root)
    def on_closing(): app.quit_driver(); root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()