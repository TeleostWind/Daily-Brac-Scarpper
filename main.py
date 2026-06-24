import json
import os
import time
import traceback
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# --- TARGET CONFIGURATION ---
WEB_TARGETS = {
    "bracu_official": "https://www.bracu.ac.bd/",
}

FB_TARGETS = {
    "bracu_fb": "bracuniversity", 
    "bucc_fb": "BRACUniversityComputerClub" 
}

def scrape_website(url):
    """Fetches text content by routing through ScraperAPI to bypass Cloudflare."""
    try:
        api_key = os.environ.get("SCRAPER_API_KEY")
        if not api_key:
            print("[!] FATAL ERROR: SCRAPER_API_KEY is missing!")
            return ""
            
        proxy_url = f"http://api.scraperapi.com?api_key={api_key}&url={url}"
        response = requests.get(proxy_url, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
            
        return soup.get_text(separator=' ', strip=True)[:30000]
    except Exception as e:
        print(f"[!] Failed to scrape website {url}: {e}")
        return ""

def scrape_facebook(account_name):
    """Fetches Facebook content by scraping the mbasic mobile site through ScraperAPI."""
    try:
        api_key = os.environ.get("SCRAPER_API_KEY")
        if not api_key:
            print("[!] FATAL ERROR: SCRAPER_API_KEY is missing!")
            return ""
            
        # Target the highly-scrappable lightweight mobile site
        url = f"https://mbasic.facebook.com/{account_name}"
        proxy_url = f"http://api.scraperapi.com?api_key={api_key}&url={url}"
        
        response = requests.get(proxy_url, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Clean out common interface noise
        for element in soup(["script", "style", "header", "footer"]):
            element.extract()
            
        return soup.get_text(separator=' ', strip=True)[:30000]
    except Exception as e:
        print(f"[!] Failed to scrape Facebook page {account_name}: {e}")
        return ""

def process_with_gemini(raw_text, source_name):
    """Sends raw text to Gemini to extract clean JSON."""
    try:
        if not os.environ.get("GEMINI_API_KEY"):
            print("[!] FATAL ERROR: GEMINI_API_KEY environment variable is missing!")
            return []

        client = genai.Client()
        prompt = f"""
        You are a data extraction assistant. Extract the most important recent news, 
        events, announcements, updates, and notices from the following text scraped from {source_name}.
        
        Return ONLY a JSON list of objects. Each object must have:
        - "title": (string) The title of the event/news/post
        - "date": (string) Date if available, otherwise "Unknown"
        - "category": (string) e.g., "Event", "Notice", "Academic", "Club Update"
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
                print(f"[SUCCESS] Data pulled from {name}! Sending to Gemini...")
                all_data[name] = process_with_gemini(raw_text, name)
            else:
                print(f"[FAILED] No text extracted for {name}.")
                
        # 2. Scrape Facebook Pages
        for name, fb_handle in FB_TARGETS.items():
            print(f"Scraping Facebook page: {name}...")
            raw_text = scrape_facebook(fb_handle)
            if raw_text:
                print(f"[SUCCESS] Data pulled from Facebook ({name})! Sending to Gemini...")
                all_data[name] = process_with_gemini(raw_text, name)
            else:
                print(f"[FAILED] No text extracted for Facebook ({name}).")
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
