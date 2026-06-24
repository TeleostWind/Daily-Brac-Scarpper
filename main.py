import json
import os
import time
import traceback
import cloudscraper
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from facebook_scraper import get_posts

# --- TARGET CONFIGURATION ---
WEB_TARGETS = {
    "bracu_official": "https://www.bracu.ac.bd/",
}

FB_TARGETS = {
    "bracu_fb": "bracuniversity", 
    "bucc_fb": "BRACUniversityComputerClub" 
}

def scrape_website(url):
    """Fetches text content, bypassing Cloudflare/WAF protections."""
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        response = scraper.get(url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
            
        return soup.get_text(separator=' ', strip=True)[:30000]
    except Exception as e:
        print(f"[!] Failed to scrape website {url}: {e}")
        return ""

def scrape_facebook(account_name):
    """Fetches recent posts from a Facebook page."""
    try:
        posts_text = []
        for post in get_posts(account_name, pages=2):
            if post.get('text'):
                date_str = post['time'].strftime("%Y-%m-%d") if post.get('time') else "Unknown Date"
                posts_text.append(f"[{date_str}] {post['text']}")
        return "\n\n".join(posts_text)[:30000]
    except Exception as e:
        print(f"[!] Failed to scrape Facebook page {account_name}: {e}")
        return ""

def process_with_gemini(raw_text, source_name):
    """Sends raw text to Gemini to extract clean JSON."""
    try:
        if not os.environ.get("GEMINI_API_KEY"):
            print("[!] FATAL ERROR: GEMINI_API_KEY environment variable is empty or missing!")
            return []

        client = genai.Client()
        prompt = f"""
        You are a data extraction assistant. Extract the most important recent news, 
        events, announcements, and notices from the following text scraped from {source_name}.
        
        Return ONLY a JSON list of objects. Each object must have:
        - "title": (string) The title of the event/news
        - "date": (string) Date if available, otherwise "Unknown"
        - "category": (string) e.g., "Event", "Notice", "Academic", "Club"
        - "summary": (string) A 1-2 sentence description
        
        Raw Text:
        {raw_text}
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[!] Gemini processing failed for {source_name}: {e}")
        return []

def main():
    try:
        all_data = {}
        print("--- Starting Scraping Run ---")
        
        # 1. Scrape Standard Websites
        for name, url in WEB_TARGETS.items():
            print(f"Scraping website: {name}...")
            raw_text = scrape_website(url)
            if raw_text:
                all_data[name] = process_with_gemini(raw_text, name)
                
        # 2. Scrape Facebook Pages
        for name, fb_handle in FB_TARGETS.items():
            print(f"Scraping Facebook: {name}...")
            raw_text = scrape_facebook(fb_handle)
            if raw_text:
                all_data[name] = process_with_gemini(raw_text, name)
            time.sleep(5)
                
        # 3. Save Final Data
        with open('bracu_data.json', 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
        print("--- Data saved successfully to bracu_data.json ---")

    except Exception as e:
        print("\n[CRITICAL ERROR] The script crashed unexpectedly:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
