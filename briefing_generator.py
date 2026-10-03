import os
import sys
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# KST timezone (+9)
KST = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY and len(sys.argv) > 1:
    GEMINI_API_KEY = sys.argv[1]

# RSS Feed sources
FEEDS = {
    "AI·테크": "https://news.google.com/rss/search?q=ChatGPT+OR+Gemini+OR+인공지능+OR+생성형AI+OR+LLM&hl=ko&gl=KR&ceid=KR:ko",
    "과학·미래": "https://news.google.com/rss/search?q=우주탐사+OR+로봇공학+OR+인공위성+OR+휴머노이드&hl=ko&gl=KR&ceid=KR:ko",
    "생활·취미": "https://news.google.com/rss/search?q=그래픽카드+OR+PC하드웨어+OR+전기차+OR+게임신작&hl=ko&gl=KR&ceid=KR:ko",
    "전국·지역": "https://news.google.com/rss/search?q=무안+OR+목포+OR+전남+OR+광주&hl=ko&gl=KR&ceid=KR:ko",
    "정치·사회": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFZ4ZERBU0FtdHZLQUFQAQ?hl=ko&gl=KR&ceid=KR:ko",
    "뉴스공장": "https://news.google.com/rss/search?q=겸손은힘들다+뉴스공장&hl=ko&gl=KR&ceid=KR:ko"
}

def fetch_rss_items(url, max_items=8):
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read()
            root = ET.fromstring(content)
            for item in root.findall('./channel/item')[:max_items]:
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                source_el = item.find('source')
                source = source_el.text if source_el is not None else "언론사"
                clean_title = title.split(" - ")[0] if " - " in title else title
                items.append({
                    "title": clean_title,
                    "link": f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(clean_title[:30])}",
                    "pubDate": pubDate,
                    "source": source
                })
    except Exception as e:
        print(f"Error fetching RSS {url}: {e}", file=sys.stderr)
    return items

def call_gemini(prompt):
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set.", file=sys.stderr)
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=50) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            text = res_json['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text)
    except Exception as e:
        print(f"Error calling Gemini: {e}", file=sys.stderr)
        return None

def main():
    print(f"[{NOW_KST.strftime('%Y-%m-%d %H:%M:%S KST')}] Starting briefing generation...")
    
    hour = NOW_KST.hour
    is_morning = 4 <= hour < 12
    edition_key = "morning" if is_morning else "afternoon"
    edition_name = "오전 6시판 (전날 16:00 ~ 당일 06:00)" if is_morning else "오후 4시판 (당일 06:00 ~ 16:00)"
    
    date_str = f"{NOW_KST.month}월 {NOW_KST.day}일 " + ["월", "화", "수", "목", "금", "토", "일"][NOW_KST.weekday()] + "요일"

    collected_data = {}
    for cat, url in FEEDS.items():
        collected_data[cat] = fetch_rss_items(url, max_items=8)

    prompt = f"""
당신은 '해적왕 뉴스룸'의 전담 AI 수석 에디터입니다.
사용자(서홍식, 해적왕)는 전남 무안 거주, 실무 관리자이며, AI 도구 활용·하드웨어·지역 뉴스·뉴스공장 방송을 주요 관심사로 봅니다.

현재 일자: {date_str}
현재 브리핑 판: {edition_name}

수집된 뉴스 데이터:
{json.dumps(collected_data, ensure_ascii=False, indent=2)}

[핵심 규칙: 토픽 클러스터링(동일 사건 묶음)]
1. 기사를 기계적으로 갯수만 채우지 마세요.
2. 수집된 뉴스 중 **동일하거나 유사한 사건·이슈를 다룬 기사들은 반드시 하나의 대표 이슈 카드로 묶으세요.**
3. 묶인 다른 언론사의 관련 기사들은 `relatedArticles` 배열에 [언론사명, 발행시각, 기사제목, 링크]로 포함하세요.
4. 독립적인 사건 단위로 카드를 생성하되, 시간 범위 내에 실제로 발생한 의미 있는 이슈들만 선별하세요 (최소 10건 ~ 최대 18건).
5. 전국·지역 분야는 무안, 목포, 전남, 광주 지역 기사를 최우선 배치하세요.

[각 기사(article) 작성 포맷]
- id: 유니크 ID (예: 'art_1')
- category: 'AI·테크', '과학·미래', '생활·취미', '전국·지역', '정치·사회', '뉴스공장' 중 하나
- badge: 세부 키워드 (예: '무안 산단', '제미나이 2.5', '고철 시세' 등)
- title: 핵심을 찌르는 직관적인 제목
- summary: 사건의 핵심 사실 요약 2~3줄
- whyMatters: 실무/일상 관점에서 왜 중요한지, 어떤 영향과 의미가 있는지
- details: 사건의 구체적 경위, 발표 내용, 핵심 수치
- facts: 확인된 사실 리스트 (1~2개)
- claims: 관계자 주장 및 전망 리스트 (1~2개)
- source: 대표 언론사명
- time: 보도 시각 (예: '10월 3일 05:40')
- originalUrl: 대표 기사 실제 검색/원문 URL
- thumb: 주제에 어울리는 고품질 Unsplash 이미지 URL
- relatedArticles: 같은 사건을 다룬 다른 언론사 기사 묶음 배열 (title, source, time, url)

반드시 위 형식의 JSON 구조로 반환하세요.
"""

    gemini_result = call_gemini(prompt)

    latest_file = os.path.join(os.path.dirname(__file__), "data", "latest.json")
    existing_data = {}
    if os.path.exists(latest_file):
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            pass

    if gemini_result and "articles" in gemini_result:
        existing_data[edition_key] = gemini_result
        print(f"Successfully generated {edition_key} edition with {len(gemini_result.get('articles', []))} clustered issues.")
    else:
        print("Gemini result failed or empty, preserving existing data.", file=sys.stderr)

    os.makedirs(os.path.dirname(latest_file), exist_ok=True)
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {latest_file}")

if __name__ == "__main__":
    main()
