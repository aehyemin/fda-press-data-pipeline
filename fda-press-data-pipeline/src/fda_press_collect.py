import json, random, time, hashlib, re, os
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
            # date = published_at[:10] #2026-01-21
            date = published_at
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

        for sel in ["header", "aside", ".row", ".text-center", ".field--label", ".field--item"]:
            for tag in main.select(sel):
                tag.decompose()
                
        text = main.get_text("\n", strip=True)
        
        if text and len(text) > 100:
            return text
        
    return ""



def main():
    driver = build_driver(headless=False)
    existing_hash = set()
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    item = json.loads(line)
                    existing_hash.add(item['url_hash'])
                except:
                    continue
    print(f"기존 데이터: {len(existing_hash)}건")
    all_scraped_articles = []
    MAX_PAGES=4
    try:
          
        for page in range(0, MAX_PAGES):
            print(f"{page}페이지 목록 확인")
            page_url = f"{LIST_URL}?page={page}"
            driver.get(page_url)
                
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/news-events/press-announcements/']"))
                )
                list_html = driver.page_source
                page_articles = parse_press_annouce(list_html)
                    

                new_in_page = [a for a in page_articles if a['url_hash'] not in existing_hash]
                all_scraped_articles.extend(new_in_page)
                    
                print(f"{page}페이지: 신규 {len(new_in_page)}건 발견 (누적 신규: {len(all_scraped_articles)}건)")
                    
                if len(page_articles) > 0 and len(new_in_page) == 0:
                    print("중복된 데이터.")
                    break
                        
            except Exception as e:
                print(f"{page} 오류: {e}")
                break 
                
            time.sleep(random.uniform(1, 1.5)) 

        if not all_scraped_articles:
            print("새로 수집할 기사가 없습니다. 프로그램 종료")
            return


        print(f"\n총 {len(all_scraped_articles)}건의 신규 본문 수집 시작")
            

        with open(SAVE_PATH, 'a', encoding='utf-8') as f:
            for i, a in enumerate(all_scraped_articles, 1):
                body = fetch_body(driver, a["url"], max_retry=3)
                a["body_en"] = body
                
                if body:

                    f.write(json.dumps(a, ensure_ascii=False) + "\n")
                    print(f"[{i}/{len(all_scraped_articles)}] 성공: {a['title'][:30]}")
                else:
                    print(f"[{i}/{len(all_scraped_articles)}] 실패: {a['title'][:30]}")
                    
                time.sleep(random.uniform(0.5, 1.0))
                    
        print(f"\n 신규 데이터 {len(all_scraped_articles)}건 적재 완료")
                
    finally:
        driver.quit()



if __name__ == "__main__":
    main()