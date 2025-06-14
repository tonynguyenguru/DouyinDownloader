import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import time
import re
import os
import webbrowser
from urllib.parse import urlparse, parse_qs
from douyin_core import DouyinDownloader

class DouyinDownloaderGUI:
    @staticmethod
    def standardize_douyin_url(url: str) -> str:
        # Ưu tiên dạng /video/ID
        match = re.search(r'/video/(\d+)', url)
        if match:
            return f"https://www.douyin.com/video/{match.group(1)}"
        # Lấy modal_id hoặc vid
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        video_id = query.get('modal_id', [None])[0] or query.get('vid', [None])[0]
        if video_id and video_id.isdigit():
            return f"https://www.douyin.com/video/{video_id}"
        # fallback: tìm số dài trong url
        match = re.search(r'(\d{10,20})', url)
        if match:
            return f"https://www.douyin.com/video/{match.group(1)}"
        return url

    def __init__(self):
        """Initialize the GUI application"""
        self.root = tk.Tk()
        self.root.title("Douyin Video Downloader By Tony Nguyen")
        self.root.geometry("1000x800")
        
        # Thêm hàm _log trước khi khởi tạo downloader
        self._log = self._default_log

        # Initialize downloader
        self.downloader = DouyinDownloader(log_callback=self._log)
        self.is_downloading = False
        self.download_thread = None
        self._create_widgets()
        self._create_context_menus()
        self._bind_shortcuts()

    def _default_log(self, message: str) -> None:
        try:
            self.log_area.insert(tk.END, str(message) + "\n")
            self.log_area.see(tk.END)
        except Exception:
            print(message)

    def _create_widgets(self):
        # Input frame
        input_frame = ttk.LabelFrame(self.root, text="Nhập Link", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        self.url_entry = ttk.Entry(input_frame)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.process_btn = ttk.Button(input_frame, text="Xử lý", command=self._process_url)
        self.process_btn.pack(side=tk.RIGHT, padx=(5,0))

        # Videos frame
        videos_frame = ttk.LabelFrame(self.root, text="Danh sách video", padding=10)
        videos_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Buttons frame - Thêm frame chứa các nút
        buttons_frame = ttk.Frame(videos_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 5))

        # Sửa lại phần tạo nút download
        self.download_btn = ttk.Button(buttons_frame, text="Tải Video Đã Chọn", 
                                     command=self._toggle_download)
        self.download_btn.pack(side=tk.LEFT, padx=5)

        # Thêm nút Load More
        self.load_more_btn = ttk.Button(buttons_frame, text="Tải Thêm Video", 
                                       command=self._load_more_videos, state='disabled')
        self.load_more_btn.pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_label = ttk.Label(buttons_frame, text="Tổng số link: 0 | Đã chọn: 0")
        self.status_label.pack(side=tk.RIGHT, padx=5)

        # Tree frame
        tree_frame = ttk.Frame(videos_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview với ScrollBar
        self.tree = ttk.Treeview(tree_frame, columns=('url',), show='headings', 
                            selectmode='extended')
        self.tree.heading('url', text='URL Video')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar cho Treeview
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Download status frame
        download_status_frame = ttk.Frame(videos_frame)
        download_status_frame.pack(fill=tk.X, pady=(5,0))

        self.download_status = ttk.Label(download_status_frame, text="")
        self.download_status.pack(side=tk.LEFT)

        self.download_progress = ttk.Progressbar(download_status_frame, 
                                           mode='determinate', 
                                           length=300)
        self.download_progress.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Trạng thái", padding=10)
        log_frame.pack(fill=tk.X, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, height=8)
        self.log_area.pack(fill=tk.X)

        # Progress bar
        self.progress = ttk.Progressbar(log_frame, mode='determinate', length=300)
        self.progress.pack(fill=tk.X, pady=(5,0))

        # Settings frame
        settings_frame = ttk.LabelFrame(self.root, text="Cài đặt", padding=10)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        # API Key input
        api_key_frame = ttk.Frame(settings_frame)
        api_key_frame.pack(fill=tk.X)
        
        ttk.Label(api_key_frame, text="Capsolver API Key:").pack(side=tk.LEFT)
        self.api_key_entry = ttk.Entry(api_key_frame, show="*", width=50)
        self.api_key_entry.insert(0, "")
        self.api_key_entry.pack(side=tk.LEFT, padx=5)
        
        # Thêm nút Test API
        ttk.Button(api_key_frame, text="Test API", 
                  command=self._test_capsolver_api).pack(side=tk.LEFT, padx=5)
        
        # Headless mode checkbox
        self.headless_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Chạy Chrome ẩn", 
                        variable=self.headless_var).pack(side=tk.LEFT, padx=5)

        # Add download folder frame
        download_frame = ttk.LabelFrame(self.root, text="Thư mục tải xuống")
        download_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.download_path = tk.StringVar(value="downloads")  # Default folder
        
        ttk.Entry(download_frame, textvariable=self.download_path, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(download_frame, text="Chọn thư mục", command=self._choose_download_folder).pack(side=tk.LEFT, padx=5)

    def _create_context_menus(self):
        # URL entry context menu
        self.url_menu = tk.Menu(self.root, tearoff=0)
        self.url_menu.add_command(label="Cắt", command=lambda: self.url_entry.event_generate("<<Cut>>"))
        self.url_menu.add_command(label="Sao chép", command=lambda: self.url_entry.event_generate("<<Copy>>"))
        self.url_menu.add_command(label="Dán", command=lambda: self.url_entry.event_generate("<<Paste>>"))
        self.url_menu.add_separator()
        self.url_menu.add_command(label="Chọn tất cả", command=lambda: self.url_entry.select_range(0, tk.END))

        # Tree context menu
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Sao chép URL", command=self._copy_selected_urls)
        self.tree_menu.add_command(label="Dán URL", command=self._paste_urls)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Chọn tất cả", command=self._select_all_items)
        self.tree_menu.add_command(label="Bỏ chọn tất cả", command=self._deselect_all_items)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Xóa đã chọn", command=self._delete_selected_items)
        self.tree_menu.add_command(label="Xóa tất cả", command=self._clear_tree)

    def _bind_shortcuts(self):
        # URL entry shortcuts
        self.url_entry.bind("<Button-3>", self._show_url_menu)
        self.url_entry.bind("<Control-a>", lambda e: self.url_entry.select_range(0, tk.END))

        # Tree shortcuts
        self.tree.bind("<Button-3>", self._show_tree_menu)
        self.tree.bind("<Control-a>", self._select_all_items)
        self.tree.bind("<Delete>", lambda e: self._delete_selected_items())
        self.tree.bind("<Control-c>", lambda e: self._copy_selected_urls())
        self.tree.bind("<Control-v>", lambda e: self._paste_urls())
        self.tree.bind("<Shift-Up>", lambda e: self._shift_select(-1))
        self.tree.bind("<Shift-Down>", lambda e: self._shift_select(1))
        # Thêm binding cho chuột trái bôi chọn
        self.tree.bind('<ButtonPress-1>', self._on_tree_click)
        self.tree.bind('<B1-Motion>', self._on_tree_drag)
        self.tree.bind('<ButtonRelease-1>', self._on_tree_release)
        
        # Binding cho selection change
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        
        # Thêm binding cho double click
        self.tree.bind('<Double-1>', self._on_double_click)

    def _process_url(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập link Douyin!")
            return
        
        self._log(f"Đã nhận link: {url}")
        
        if '/user/' in url:
            self._log("Đang xử lý link user...")
            threading.Thread(target=self._process_user_videos, args=(url,)).start()
            return
        
        standard_url = self.standardize_douyin_url(url)  # Updated reference
        if standard_url:
            if not self._is_url_exists(standard_url):
                self.tree.insert('', 'end', values=(standard_url,))
                self._log("Đã thêm URL vào danh sách")
                self._update_status_label()
            else:
                self._log("URL đã tồn tại trong danh sách")
        else:
            self._log("Không thể chuyển đổi link về định dạng chuẩn")

    def _process_user_videos(self, user_url):
        try:
            self.current_user_url = user_url  # Lưu URL user hiện tại
            self.video_start_index = 0  # Reset index
            
            # Lấy API key từ entry
            capsolver_key = self.api_key_entry.get().strip()
            
            # Chỉ chạy headless nếu có API key hợp lệ
            headless = self.headless_var.get() and capsolver_key and len(capsolver_key) > 10
            
            self.downloader = DouyinDownloader(
                log_callback=self._log,
                capsolver_key=capsolver_key,
                headless=headless
            )
            
            # Lấy 20 video đầu tiên
            videos = self.downloader.get_user_videos(user_url, start_index=0, batch_size=20)
            
            # Thêm videos vào bảng
            added_count = 0
            for video in videos:
                if not self._is_url_exists(video['url']):
                    self.tree.insert('', 'end', values=(video['url'],))
                    added_count += 1
                    
            if added_count > 0:
                self._log(f"Đã thêm {added_count} video mới")
                self.video_start_index += added_count
                self.load_more_btn.config(state='normal')  # Enable nút Load More
            else:
                self._log("Không tìm thấy video mới")
                
        except Exception as e:
            self._log(f"Lỗi khi xử lý videos từ user: {str(e)}")
            messagebox.showerror("Lỗi", f"Không thể lấy danh sách video: {str(e)}")
        finally:
            self.process_btn.config(state='normal')
            self.download_status.config(text="")
            self._update_status_label()

    def _load_more_videos(self):
        """Tải thêm 20 video tiếp theo"""
        if hasattr(self, 'current_user_url'):
            try:
                self.load_more_btn.config(state='disabled')
                self._log("Đang tải thêm video...")
                
                videos = self.downloader.get_user_videos(
                    self.current_user_url, 
                    start_index=self.video_start_index,
                    batch_size=20
                )
                
                added_count = 0
                for video in videos:
                    if not self._is_url_exists(video['url']):
                        self.tree.insert('', 'end', values=(video['url'],))
                        added_count += 1
                        
                if added_count > 0:
                    self._log(f"Đã thêm {added_count} video mới")
                    self.video_start_index += added_count
                    self.load_more_btn.config(state='normal')
                else:
                    self._log("Không còn video mới để tải")
                    
            except Exception as e:
                self._log(f"Lỗi khi tải thêm video: {str(e)}")
                messagebox.showerror("Lỗi", f"Không thể tải thêm video: {str(e)}")
            finally:
                self._update_status_label()

    def _is_url_exists(self, url):
        for item in self.tree.get_children():
            if self.tree.item(item, 'values')[0] == url:
                return True
        return False

    def _create_widgets(self):
        # Input frame
        input_frame = ttk.LabelFrame(self.root, text="Nhập Link", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        self.url_entry = ttk.Entry(input_frame)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.process_btn = ttk.Button(input_frame, text="Xử lý", command=self._process_url)
        self.process_btn.pack(side=tk.RIGHT, padx=(5,0))

        # Videos frame
        videos_frame = ttk.LabelFrame(self.root, text="Danh sách video", padding=10)
        videos_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Buttons frame - Thêm frame chứa các nút
        buttons_frame = ttk.Frame(videos_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 5))

        # Sửa lại phần tạo nút download
        self.download_btn = ttk.Button(buttons_frame, text="Tải Video Đã Chọn", 
                                     command=self._toggle_download)
        self.download_btn.pack(side=tk.LEFT, padx=5)

        # Thêm nút Load More
        self.load_more_btn = ttk.Button(buttons_frame, text="Tải Thêm Video", 
                                       command=self._load_more_videos, state='disabled')
        self.load_more_btn.pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_label = ttk.Label(buttons_frame, text="Tổng số link: 0 | Đã chọn: 0")
        self.status_label.pack(side=tk.RIGHT, padx=5)

        # Tree frame
        tree_frame = ttk.Frame(videos_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview với ScrollBar
        self.tree = ttk.Treeview(tree_frame, columns=('url',), show='headings', 
                            selectmode='extended')
        self.tree.heading('url', text='URL Video')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar cho Treeview
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Download status frame
        download_status_frame = ttk.Frame(videos_frame)
        download_status_frame.pack(fill=tk.X, pady=(5,0))

        self.download_status = ttk.Label(download_status_frame, text="")
        self.download_status.pack(side=tk.LEFT)

        self.download_progress = ttk.Progressbar(download_status_frame, 
                                           mode='determinate', 
                                           length=300)
        self.download_progress.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Trạng thái", padding=10)
        log_frame.pack(fill=tk.X, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, height=8)
        self.log_area.pack(fill=tk.X)

        # Progress bar
        self.progress = ttk.Progressbar(log_frame, mode='determinate', length=300)
        self.progress.pack(fill=tk.X, pady=(5,0))

        # Settings frame
        settings_frame = ttk.LabelFrame(self.root, text="Cài đặt", padding=10)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        # API Key input
        api_key_frame = ttk.Frame(settings_frame)
        api_key_frame.pack(fill=tk.X)
        
        ttk.Label(api_key_frame, text="Capsolver API Key:").pack(side=tk.LEFT)
        self.api_key_entry = ttk.Entry(api_key_frame, show="*", width=50)
        self.api_key_entry.insert(0, "")
        self.api_key_entry.pack(side=tk.LEFT, padx=5)
        
        # Thêm nút Test API
        ttk.Button(api_key_frame, text="Test API", 
                  command=self._test_capsolver_api).pack(side=tk.LEFT, padx=5)
        
        # Headless mode checkbox
        self.headless_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Chạy Chrome ẩn", 
                        variable=self.headless_var).pack(side=tk.LEFT, padx=5)

        # Add download folder frame
        download_frame = ttk.LabelFrame(self.root, text="Thư mục tải xuống")
        download_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.download_path = tk.StringVar(value="downloads")  # Default folder
        
        ttk.Entry(download_frame, textvariable=self.download_path, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(download_frame, text="Chọn thư mục", command=self._choose_download_folder).pack(side=tk.LEFT, padx=5)

    def _choose_download_folder(self) -> None:
        """Choose download folder"""
        folder = filedialog.askdirectory(title="Chọn thư mục tải xuống")
        if folder:
            self.download_path.set(folder)

    def _toggle_download(self):
        """Chuyển đổi giữa tải và dừng tải"""
        if not self.is_downloading:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn video cần tải!")
                return
                
            download_path = self.download_path.get().strip()
            if not download_path:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn thư mục tải xuống!")
                return
                
            urls = [self.tree.item(item)['values'][0] for item in selected]
            self.is_downloading = True
            self.download_btn.config(text="Dừng")
            threading.Thread(target=self._download_multiple_videos, args=(urls, download_path)).start()
        else:
            self.is_downloading = False
            self.download_btn.config(text="Tải Video")

    def _download_multiple_videos(self, urls, download_path):
        try:
            total = len(urls)
            success = 0
            
            for i, url in enumerate(urls, 1):
                if not self.is_downloading:
                    break
                    
                self.download_status.config(text=f"Đang tải {i}/{total}")
                
                # Retry up to 3 times for each video
                for attempt in range(3):
                    if self.downloader.download_video(url, download_path=download_path):
                        success += 1
                        break
                    elif attempt < 2:  # Don't sleep on last attempt
                        time.sleep(2)
                        
            self._log(f"Đã tải xong {success}/{total} video")
            
        except Exception as e:
            self._log(f"Lỗi khi tải video: {str(e)}")
        finally:
            self.is_downloading = False
            self.download_btn.config(text="Tải Video")
            self.download_status.config(text="")

    def _copy_selected_urls(self):
        urls = [self.tree.item(item, 'values')[0] for item in self.tree.selection()]
        if urls:
            self.root.clipboard_clear()
            self.root.clipboard_append('\n'.join(urls))
            self._log("Đã sao chép URL vào clipboard")

    def _paste_urls(self) -> None:
        try:
            data = self.root.clipboard_get()
            for url in data.splitlines():
                url = url.strip()
                if url:
                    std_url = self.standardize_douyin_url(url)  # Updated reference
                    if std_url and not self._is_url_exists(std_url):
                        self.tree.insert('', 'end', values=(std_url,))
            self._log("Đã dán URL từ clipboard")
            self._update_status_label()
        except Exception:
            pass

    def _select_all_items(self, event=None):
        self.tree.selection_set(self.tree.get_children())

    def _deselect_all_items(self):
        self.tree.selection_remove(self.tree.get_children())

    def _delete_selected_items(self):
        for item in self.tree.selection():
            self.tree.delete(item)
        self._log("Đã xóa các URL đã chọn")
        self._update_status_label()  # Cập nhật status sau khi xóa

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._log("Đã xóa toàn bộ danh sách")
        self._update_status_label()  # Cập nhật status sau khi xóa

    def _show_url_menu(self, event):
        self.url_menu.tk_popup(event.x_root, event.y_root)

    def _show_tree_menu(self, event):
        self.tree_menu.tk_popup(event.x_root, event.y_root)

    def _shift_select(self, direction):
        selected = self.tree.selection()
        items = self.tree.get_children()
        if not selected:
            return
        idx = items.index(selected[-1])
        new_idx = max(0, min(len(items)-1, idx + direction))
        self.tree.selection_set(items[new_idx])

    def _update_status_label(self):
        total = len(self.tree.get_children())
        selected = len(self.tree.selection())
        self.status_label.config(text=f"Tổng số link: {total} | Đã chọn: {selected}")

    def _on_tree_click(self, event):
        self.tree.selection_set(self.tree.identify_row(event.y))
        self._drag_start_item = self.tree.identify_row(event.y)

    def _on_tree_drag(self, event):
        if hasattr(self, '_drag_start_item'):
            current_item = self.tree.identify_row(event.y)
            if current_item and current_item != self._drag_start_item:
                items = self.tree.get_children()
                start_idx = items.index(self._drag_start_item)
                current_idx = items.index(current_item)
                
                # Chọn tất cả items trong khoảng
                min_idx = min(start_idx, current_idx)
                max_idx = max(start_idx, current_idx)
                to_select = items[min_idx:max_idx+1]
                
                self.tree.selection_set(to_select)
                self._update_status_label()

    def _on_tree_release(self, event):
        if hasattr(self, '_drag_start_item'):
            delattr(self, '_drag_start_item')

    def _on_tree_select(self, event=None):
        self._update_status_label()

    def _on_double_click(self, event):
        """Xử lý sự kiện double click vào link"""
        item = self.tree.selection()[0]  # Lấy item được chọn
        url = self.tree.item(item, 'values')[0]  # Lấy URL từ item
        try:
            webbrowser.open(url)  # Mở URL trong trình duyệt mặc định
        except Exception as e:
            self._log(f"Không thể mở link: {str(e)}")

    def _test_capsolver_api(self) -> None:
        """Test API key Capsolver"""
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập API key!")
            return
            
        self._log("Đang test Capsolver API...")
        self.downloader.capsolver_key = api_key
        threading.Thread(target=self.downloader.test_capsolver).start()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = DouyinDownloaderGUI()
    app.run()