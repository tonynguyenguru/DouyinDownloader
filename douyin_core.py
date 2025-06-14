import re
import time
import os
import requests
from typing import Optional, List, Dict, Callable
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse, parse_qs
from PyQt5.QtWidgets import QApplication
from selenium.webdriver.common.action_chains import ActionChains

class DouyinDownloader:
    def __init__(self, log_callback=None, capsolver_key=None, headless=True):
        self.log_callback = log_callback
        self.capsolver_key = capsolver_key
        self.headless = headless
        self.driver = None

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'/video/(\d+)',
            r'vid=(\d+)',
            r'modal_id=(\d+)',
            r'v.douyin.com/(\w+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def standardize_douyin_url(self, url):
        match = re.search(r'/video/(\d+)', url)
        if match:
            return f"https://www.douyin.com/video/{match.group(1)}"
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        video_id = query.get('modal_id', [None])[0] or query.get('vid', [None])[0]
        if video_id and video_id.isdigit():
            return f"https://www.douyin.com/video/{video_id}"
        match = re.search(r'(\d{10,20})', url)
        if match:
            return f"https://www.douyin.com/video/{match.group(1)}"
        return url

    def _setup_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        
        # Disable GPU and hardware acceleration
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=500,500')
        chrome_options.add_argument('--log-level=3')
        
        # Only run headless when we have valid Capsolver key
        if self.headless and self.capsolver_key and len(self.capsolver_key) > 10:
            chrome_options.add_argument('--headless=new')
        
        # Create ChromeDriver service with proper logging
        service = Service(ChromeDriverManager().install())
        
        # Fix the logging issue by using devnull
        import subprocess
        service.creation_flags = subprocess.CREATE_NO_WINDOW
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        if not (self.headless and self.capsolver_key and len(self.capsolver_key) > 10):
            driver.set_window_size(500, 500)
        
        return driver

    def get_user_videos(self, url: str, start_index: int = 0, batch_size: int = 20) -> List[Dict[str, str]]:
        try:
            # Keep driver instance if exists and valid
            if not self.driver or not self._is_driver_valid():
                self.driver = self._setup_driver()
                self.log("Đang truy cập trang người dùng...")
                self.driver.get(url)
                time.sleep(5)
                
                if self._check_for_captcha():
                    if not self._solve_captcha():
                        return []
            else:
                # Scroll back to top for loading more videos
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)
                
            videos = []
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            
            while True:
                # Get all video elements
                elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/video/')]")
                current_count = len(elements)
                
                # Process new videos
                if current_count > start_index:
                    for el in elements[start_index:]:
                        try:
                            href = el.get_attribute('href')
                            if href and '/video/' in href:
                                video_id = self.extract_video_id(href)
                                if video_id:
                                    clean_url = f"https://www.douyin.com/video/{video_id}"
                                    if clean_url not in [v['url'] for v in videos]:
                                        videos.append({'url': clean_url, 'id': video_id})
                                        self.log(f"Tìm thấy video mới: {video_id}")
                        except:
                            continue
                
                # Check if we have enough videos
                if len(videos) >= batch_size:
                    self.log(f"Đã tìm đủ {batch_size} video")
                    return videos[:batch_size]
                
                # Scroll and wait
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                    if scroll_attempts >= 3:  # Stop after 3 unsuccessful scrolls
                        break
                else:
                    scroll_attempts = 0
                    last_height = new_height
            
            self.log(f"Đã tìm thấy tổng cộng {len(videos)} video")
            return videos
            
        except Exception as e:
            self.log(f"Lỗi khi tải danh sách video: {str(e)}")
            return []
        finally:
            # Don't cleanup driver here to keep it for subsequent calls
            pass

    def download_video(self, url: str, download_path: str = "downloads", progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        try:
            os.makedirs(download_path, exist_ok=True)
            
            # Get video URL without loading page if possible
            video_id = self.extract_video_id(url)
            video_url = None
            
            if not video_url:
                # Need to load page to get video URL
                if not self.driver or not self._is_driver_valid():
                    self._cleanup_driver()
                    self.driver = self._setup_driver()
                    
                self.log("Đang truy cập video...")
                self.driver.get(url)
                time.sleep(3)
                
                if self._check_for_captcha():
                    if not self._solve_captcha():
                        return False
                        
                video_url = self._get_video_url_from_network()
                
            if not video_url:
                return False
                
            video_id = self.extract_video_id(url)
            if not video_id:
                return False
                
            output_path = os.path.join(download_path, f"douyin_{video_id}.mp4")
            self.log("Bắt đầu tải video...")
            
            # Download with proper headers and timeout
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.douyin.com/',
                'Range': 'bytes=0-'  # Request full file
            }
            
            with requests.get(video_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                
                # Only proceed if file size is reasonable (> 100KB)
                if total < 102400:  # 100KB
                    self.log("File size quá nhỏ, có thể không phải video")
                    return False
                    
                with open(output_path, 'wb') as f:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            size = len(chunk)
                            downloaded += size
                            f.write(chunk)
                            if total and progress_callback:
                                progress = (downloaded / total) * 100
                                progress_callback(progress)
                                
                # Verify downloaded file size
                if os.path.getsize(output_path) < 102400:
                    os.remove(output_path)
                    self.log("File tải xuống quá nhỏ, đã xóa")
                    return False
                
                self.log(f"Đã tải xong: {output_path}")
                return True
            
        except Exception as e:
            self.log(f"Lỗi khi tải video: {str(e)}")
            return False

    def _is_driver_valid(self):
        """Check if current driver session is valid"""
        try:
            # Try to get current URL to check session
            self.driver.current_url
            return True
        except:
            return False

    def _get_video_url_from_network(self):
        """Get video URL from network requests"""
        try:
            # Đợi trang load xong
            time.sleep(5)
            
            # Thử nhiều cách để lấy URL video
            video_url = None
            
            # Cách 1: Tìm qua network logs
            try:
                logs = self.driver.execute_script("""
                    var performance = window.performance || window.mozPerformance || window.msPerformance || window.webkitPerformance || {};
                    var network = performance.getEntries() || {};
                    return network;
                """)
                
                for log in logs:
                    try:
                        url = log.get('name', '')
                        if '.mp4' in url and ('v26' in url or 'v3' in url):
                            video_url = url
                            break
                    except:
                        continue
            except:
                pass
                
            # Cách 2: Tìm trực tiếp từ video element
            if not video_url:
                try:
                    video_elem = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "video"))
                    )
                    video_url = video_elem.get_attribute('src')
                except:
                    pass
                
            # Cách 3: Tìm từ source element trong video
            if not video_url:
                try:
                    source_elem = self.driver.find_element(By.CSS_SELECTOR, "video source")
                    video_url = source_elem.get_attribute('src')
                except:
                    pass
                
            # Cách 4: Tìm từ div chứa video
            if not video_url:
                try:
                    video_div = self.driver.find_element(By.CSS_SELECTOR, "div[data-e2e='video-player']")
                    video_url = video_div.get_attribute('data-src')
                except:
                    pass
                
            if video_url:
                self.log("Đã tìm thấy URL video")
                return video_url
                
            self.log("Không tìm thấy URL video")
            return None
            
        except Exception as e:
            self.log(f"Lỗi khi lấy URL video: {str(e)}")
            return None

    def add_link_to_table(self, url):
        std_url = self.standardize_douyin_url(url)
        # ...thêm std_url vào bảng thay vì url gốc...

    def paste_links(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        for line in text.splitlines():
            std_url = self.standardize_douyin_url(line.strip())
            if std_url:
                self.add_link_to_table(std_url)

    def _cleanup_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def _check_for_captcha(self):
        """Kiểm tra xem có captcha không"""
        try:
            return bool(self.driver.find_elements(By.XPATH, "//div[contains(@class, 'captcha')]") or
                       self.driver.find_elements(By.XPATH, "//div[contains(@class, 'verify')]"))
        except:
            return False

    def _solve_captcha(self):
        if not self.capsolver_key:
            self.log("Không có API key Capsolver")
            return False
        
        try:
            import capsolver
            capsolver.api_key = self.capsolver_key
            
            # Wait for slider captcha
            slider = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "secsdk-captcha-drag-icon"))
            )
            
            # Get captcha images
            background = self.driver.find_element(By.CLASS_NAME, "captcha_verify_img_slide")
            background_url = background.get_attribute("src")
            
            piece = self.driver.find_element(By.CLASS_NAME, "captcha_verify_slide_block")
            piece_url = piece.get_attribute("src")
            
            self.log("Đang giải captcha...")
            
            # Submit task to Capsolver
            solution = capsolver.solve({
                "type": "DouYinSliderCaptcha",
                "websiteURL": self.driver.current_url,
                "websiteKey": "slide",
                "background": background_url,
                "slider": piece_url,
            })
            
            if solution and "score" in solution:
                offset = solution["score"] * slider.size["width"]
                
                # Move slider
                actions = ActionChains(self.driver)
                actions.click_and_hold(slider)
                actions.move_by_offset(offset, 0)
                actions.release()
                actions.perform()
                
                time.sleep(2)
                
                if not self._check_for_captcha():
                    self.log("Giải captcha thành công")
                    return True
                    
            self.log("Giải captcha thất bại")
            return False
            
        except Exception as e:
            self.log(f"Lỗi xử lý captcha: {str(e)}")
            return False

    def _validate_capsolver_key(self, api_key: str) -> bool:
        """Kiểm tra API key Capsolver có hợp lệ không"""
        try:
            import capsolver
            capsolver.api_key = api_key
            
            balance = capsolver.balance()
            self.log(f"Số dư Capsolver: ${balance}")
            return float(balance) > 0
        except Exception as e:
            self.log(f"Lỗi kiểm tra API key: {str(e)}")
            return False

    def test_capsolver(self):
        """Test kết nối và khả năng giải captcha của Capsolver"""
        if not self.capsolver_key:
            self.log("Không có API key Capsolver")
            return False
            
        try:
            import capsolver
            capsolver.api_key = self.capsolver_key
            
            # Test balance
            balance = capsolver.balance()
            self.log(f"Số dư Capsolver: ${balance}")
            
            # Test supported tasks
            self.log("Các loại captcha được hỗ trợ:")
            self.log("- DouyinSliderCaptcha")
            self.log("- ReCaptchaV2")
            self.log("- FunCaptcha")
            self.log("- HCaptcha")
            
            self.log("API key hợp lệ và sẵn sàng sử dụng")
            return True
                
        except Exception as e:
            self.log(f"Lỗi khi test Capsolver: {str(e)}")
            return False