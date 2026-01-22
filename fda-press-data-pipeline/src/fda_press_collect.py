import json, random, time, hashlib
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


#fda는 requests로 긁으면 차단됨, selenium으로 접속해서 가져오기
# 1.브라우저 준비: build_driver()
# 2.목록 페이지 HTML 가져오기: get_list_html()
# 3.목록 HTML에서 기사 메타 추출: parse_press_announce()
# 4.상세 페이지 들어가서 본문 긁기: fetch_body()
# 5.전체 실행 흐름 제어 + 파일 저장: main()

BASE_URL = "https://www.fda.gov"
LIST_URL = "https://www.fda.gov/news-events/fda-newsroom/press-announcements"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
SAVE_PATH = r"fda-press-data-pipeline\data\raw\raw_articles.jsonl"


def build_driver(headless:bool = False) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
        
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument(f"user-agent={UA}")
    
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
        )


def get_list_html(driver: webdriver.Chrome) -> str:
    driver.get(LIST_URL)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(., 'Press Announcements')]"))
    )
    return driver.page_source


def parse_press_annouce(list_html: str) -> list[dict]:
    #  <time datetime="2026-01-21T15:00:00Z">
    soup = BeautifulSoup(list_html, 'lxml')
    links = soup.select('a[href^="/news-events/press-announcements/"]')
    
    result = []
    sets = set()
    for a in links:
        href = (a.get('href') or '').strip()
        if not href or href in sets:
            continue
        sets.add(href)
            
        timeline = a.find("time")
        if timeline and timeline.has_attr("datetime"):
            published_at = timeline["datetime"] #2026-01-21T15:00:00Z
            date = published_at[:10] #2026-01-21
        else:
            published_at = ""
            date = ""
        
        text =  " ".join(a.get_text(" ", strip=True).split())
        if " - " in text:
            _, title = text.split(" - ", 1)
        else:
            title = text
        
        full_url = urljoin(BASE_URL, href)
        url_hash = hashlib.md5(full_url.encode('utf-8')).hexdigest()
         
        result.append(
            {
                "url_hash": url_hash,
                "title": title.strip(),
                "date": date,
                "published_at": published_at,
                "url": full_url,
                "source": "fda_press",
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        
    return result


#본문 텍스트 가져오기 
# https://www.fda.gov/news-events/press-announcements/ + 기사 제목
def fetch_body(driver: webdriver.Chrome, url: str, max_retry: int=3) -> str:
    for attempt in range(max_retry):
        driver.get(url)
        
        time.sleep(random.uniform(2.0, 3.0))
        cur = (driver.current_url or "").lower()
        
        if "page-not-found" in cur:
            time.sleep(attempt * 3)
            continue
        
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
            )
        except Exception:
            time.sleep(attempt * 3)
            continue
        
        soup = BeautifulSoup(driver.page_source, "lxml")
        main = soup.select_one("main") or soup

        # 불필요한 영역 제거(네비/푸터/스크립트 등)
        for sel in ["header", "aside", ".row", ".text-center", ".field--label", ".field--item"]:
            for tag in main.select(sel):
                tag.decompose()
                
        text = main.get_text("\n", strip=True)
        
        if text and len(text) > 100:
            return text
        
    return ""



def main():
    driver = build_driver(headless=False)
    
    try:
        list_html = get_list_html(driver)
        articles = parse_press_annouce(list_html)
        articles = sorted(
            articles,
            key=lambda x:x["date"] if len(x.get("date", "")) == 10 else "0000-00-00",
            reverse=True,
        )
        
        N = 10
        articles = articles[:10]
        print(f"목록수집: {len(articles)}건")
        
        for i, a in enumerate(articles, 1):
            body = fetch_body(driver, a["url"], max_retry=3)
            a["body_en"] = body
        
            if body:
                print(f"{i}/{len(articles)} 성공: {a['title'][:30]}")
            else:
                print(f"{i}/{len(articles)} 실패: {a['title'][:30]}")
                
        with open(SAVE_PATH, 'w', encoding='utf-8') as f:
            for a in articles:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
                
        print("raw_articels.jsonl 저장(본문)")
            
    finally:
        driver.quit()



if __name__ == "__main__":
    main()