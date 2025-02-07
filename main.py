import os
import sys
import time
import json
import argparse
import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from concurrent.futures import ThreadPoolExecutor

# 設定 argparse 來接收 GitHub Actions 參數
parser = argparse.ArgumentParser(description="Facebook Ads Image Scraper")
parser.add_argument("--json_file", required=True, help="Path to JSON file")
parser.add_argument("--output_dir", default="ads_media", help="Directory to save images")
args = parser.parse_args()

# 設定 ChromeDriver 路徑
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"

# 讀取 JSON 檔案
json_file = args.json_file
output_dir = args.output_dir

if not os.path.exists(json_file):
    print(f"❌ JSON 檔案不存在: {json_file}")
    sys.exit(1)

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

if len(data) == 0:
    print("❌ JSON 檔案為空")

# 解析 JSON
data_list = []
for entry in data:
    ad_id = entry.get("id", "")
    ad_title = entry.get("ad_creative_link_titles", [""])[0] if "ad_creative_link_titles" in entry else ""
    ad_text = entry.get("ad_creative_bodies", [""])[0] if "ad_creative_bodies" in entry else ""
    ad_image_url = entry.get("ad_snapshot_url", "")

    data_list.append({
        "ad_id": ad_id,
        "ad_title": ad_title,
        "ad_text": ad_text,
        "ad_image_url": ad_image_url
    })

df_ads = pd.DataFrame(data_list)

# 設定 Selenium 瀏覽器
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

service = Service(CHROMEDRIVER_PATH)
browser = webdriver.Chrome(service=service, options=chrome_options)

# 下載圖片函數
def download_image(url, folder_name, file_name):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            os.makedirs(folder_name, exist_ok=True)
            file_path = os.path.join(folder_name, file_name)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"✅ 下載成功: {file_path}")
            return file_path
        else:
            print(f"❌ 無法下載: {url}")
            return None
    except Exception as e:
        print(f"⚠️ 下載錯誤: {e}")
        return None

# 擷取 Facebook 廣告圖片
def scrape_facebook_ad(ad_url, folder_name, ad_id):
    browser.get(ad_url)
    time.sleep(5)

    soup = BeautifulSoup(browser.page_source, "html.parser")

    # 找到廣告內容的 class
    ad_container = soup.find("div", class_="_8n-d")
    if not ad_container:
        print(f"⚠️ 廣告 {ad_id} 沒有找到內容")
        return None

    # 取得所有圖片
    images = ad_container.find_all("img")
    ad_folder = os.path.join(folder_name, ad_id)  # 每個廣告 ID 建立獨立資料夾
    os.makedirs(ad_folder, exist_ok=True)

    for i, img in enumerate(images):
        img_url = img["src"]
        file_name = f"image_{i}.jpg"
        download_image(img_url, ad_folder, file_name)

    print(f"🎯 廣告 {ad_id} 下載完成！")

# 使用多線程處理所有廣告
def process_ad(row):
    if row["ad_image_url"]:
        scrape_facebook_ad(row["ad_image_url"], output_dir, row["ad_id"])

with ThreadPoolExecutor(max_workers=5) as executor:  # 最多 5 條線程
    executor.map(process_ad, [row for _, row in df_ads.iterrows()])

browser.quit()
