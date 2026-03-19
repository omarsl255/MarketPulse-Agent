import requests
from bs4 import BeautifulSoup
import time

def fetch_page_content(url: str) -> str:
    """Fetches a URL and returns the visible text content."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fetching target: {url}")
        
        # Adding a short delay to mimic human behavior
        time.sleep(1)
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        # Get text
        text = soup.get_text(separator=' ', strip=True)
        # Collapse multiple spaces
        text = ' '.join(text.split())
        return text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

if __name__ == "__main__":
    # Test target for Developer APIs / Subdomains
    url = "https://developer.siemens.com/"
    print("Testing collector on:", url)
    content = fetch_page_content(url)
    print("Extracted content length:", len(content))
    print("Snippet:", content[:500])
