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

# Get Gemini API Key from environment or argument
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY and len(sys.argv) > 1:
    GEMINI_API_KEY = sys.argv[1]

# RSS Feed sources
FEEDS = {
    "AI·테크": "https://news.google.com/rss/search?q=ChatGPT+OR+Gemini+OR+인공지능+OR+생성형AI&hl=ko&gl=KR&ceid=KR:ko",
    "과학·미래": "https://news.google.com/rss/search?q=우주탐사+OR+로봇공학+OR+인공위성&hl=ko&gl=KR&ceid=KR:ko",
    "생활·취미": "https://news.google.com/rss/search?q=그래픽카드+OR+PC하드웨어+OR+전기차&hl=ko&gl=KR&ceid=KR:ko",
    "전국·지역": "https://news.google.com/rss/search?q=무안+OR+목포+OR+전남+OR+광주&hl=ko&gl=KR&ceid=KR:ko",
    "정치·사회": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFZ4ZERBU0FtdHZLQUFQAQ?hl=ko&gl=KR&ceid=KR:ko",
    "뉴스공장": "https://news.google.com/rss/search?q=겸손은힘들다+뉴스공장&hl=ko&gl=KR&ceid=KR:ko"
}

def fetch_rss_items(url, max_items=4):
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            root = ET.fromstring(content)
            for item in root.findall('./channel/item')[:max_items]:
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                source_el = item.find('source')
                source = source_el.text if source_el is not None else "Google News"
                items.append({
                    "title": title,
                    "link": link,
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
        with urllib.request.urlopen(req, timeout=40) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            text = res_json['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text)
    except Exception as e:
        print(f"Error calling Gemini: {e}", file=sys.stderr)
        return None

def main():
    print(f"[{NOW_KST.strftime('%Y-%m-%d %H:%M:%S KST')}] Starting briefing generation...")
    
    # Determine edition: 04:00~11:59 -> morning, 12:00~23:59 or 00:00~03:59 -> afternoon
    hour = NOW_KST.hour
    is_morning = 4 <= hour < 12
    edition_key = "morning" if is_morning else "afternoon"
    edition_name = "오전 6시판 (전날 16:00 ~ 당일 06:00)" if is_morning else "오후 4시판 (당일 06:00 ~ 16:00)"
    
    date_str = f"{NOW_KST.month}월 {NOW_KST.day}일 " + ["월", "화", "수", "목", "금", "토", "일"][NOW_KST.weekday()] + "요일"

    collected_data = {}
    for cat, url in FEEDS.items():
        collected_data[cat] = fetch_rss_items(url, max_items=5)

    prompt = f"""
당신은 '해적왕 뉴스룸'의 전담 AI 수석 에디터입니다.
사용자(서홍식, 해적왕)는 전남 무안 거주, 실무 관리자이며, AI 도구 활용·하드웨어·지역 뉴스·뉴스공장 방송을 주요 관심사로 봅니다.

현재 일자: {date_str}
현재 브리핑 판: {edition_name}

다음 수집된 원문 뉴스 헤드라인 목록을 바탕으로, 엄선된 6개의 뉴스 브리핑과 뉴스공장 요약을 JSON 형식으로 작성하세요.

수집된 뉴스 데이터:
{json.dumps(collected_data, ensure_ascii=False, indent=2)}

[요구사항]
1. articles (총 6개 기사):
   - AI·테크 (최소 2개), 과학·미래, 생활·취미, 전국·지역(무안·목포·전남 우선), 정치·사회로 균형 구성
   - 각 기사는 3단계 읽기 구조를 철저히 지킵니다:
     - title: 흥미를 끄는 정확한 제목
     - summary: 2~3줄의 핵심 요약
     - whyMatters: 왜 중요한지, 나에게 어떤 영향과 실무적 의미가 있는지
     - background: 구체적 배경과 사실 관계 (추측 금지)
     - impact: 향후 예상되는 파급 영향
     - category: 'AI·테크', '과학·미래', '생활·취미', '전국·지역', '정치·사회', '뉴스공장' 중 하나
     - badge: 세부 키워드 (예: '생성형 AI', '무안·전남', '하드웨어' 등)
     - source: 원문 언론사명
     - time: 발행 시각 (예: '10월 3일 05:40')
     - originalUrl: 원문 링크 (수집된 link 사용)
     - thumb: 관련성 높은 Unsplash 이미지 URL

2. newsfactory:
   - items 3개: '오늘의 핵심 쟁점', '주요 코너 자세히', '관련 해외 보도'
   - 주장과 확인된 사실을 분리하여 객관적 시각 제공

3. soop:
   - items 2~3개: 스트리머 방송 및 대회/협업 관련 요약

반드시 다음 JSON 구조로만 반환하세요:
{{
  "date": "{date_str}",
  "edition": "{edition_name}",
  "articles": [
    {{
      "id": "item1",
      "category": "AI·테크",
      "badge": "제미나이 2.5",
      "title": "...",
      "summary": "...",
      "source": "...",
      "time": "...",
      "thumb": "https://images.unsplash.com/...",
      "whyMatters": "...",
      "background": "...",
      "impact": "...",
      "originalUrl": "..."
    }}
  ],
  "newsfactory": {{
    "items": [
      {{ "title": "오늘의 핵심 쟁점", "desc": "...", "type": "core" }}
    ]
  }},
  "soop": [
    {{ "name": "...", "desc": "...", "tag": "..." }}
  ]
}}
"""

    gemini_result = call_gemini(prompt)

    # Read existing latest.json if available
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
        print(f"Successfully generated {edition_key} edition with {len(gemini_result.get('articles', []))} articles.")
    else:
        print("Gemini result failed or empty, preserving existing data.", file=sys.stderr)

    os.makedirs(os.path.dirname(latest_file), exist_ok=True)
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {latest_file}")

if __name__ == "__main__":
    main()
