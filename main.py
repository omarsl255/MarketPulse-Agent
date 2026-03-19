import os
import uuid
from datetime import datetime
from collector import fetch_page_content
from extractor import extract_events_from_text
from db import init_db, save_event
from schema import CompetitorEvent

TARGETS = [
    "https://developer.siemens.com/"
    # Add more URLs here as needed
]

def run_pipeline():
    print("Starting Early-Warning Intelligence Pipeline...")
    init_db()
    
    for url in TARGETS:
        print("---------------------------------------------------")
        # 1. Collect
        content = fetch_page_content(url)
        if not content:
            print(f"Failed to fetch content from {url}")
            continue
            
        print(f"Fetched {len(content)} characters from {url}")
        
        # 2. Extract
        if os.environ.get("GOOGLE_API_KEY"):
            event = extract_events_from_text(content, url)
        else:
            print("No GOOGLE_API_KEY found. Generating a mock event for demonstration purposes.")
            # Fallback for prototype demonstration
            event = CompetitorEvent(
                event_id=str(uuid.uuid4()),
                competitor="Siemens",
                event_type="API_UPDATE_MOCK",
                title="Mock: Siemens Developer Portal Update",
                description=f"Detected changes on {url} (Extracted {len(content)} characters of text).",
                strategic_implication="Siemens is continuing to invest in their developer ecosystem, which poses a long-term threat to ABB's software stickiness.",
                confidence_score=0.4,
                source_url=url,
                date_detected=datetime.now().isoformat()
            )
            
        # 3. Store
        if event:
            save_event(event)
            print(f"Saved event: {event.title} (Confidence: {event.confidence_score})")

if __name__ == "__main__":
    run_pipeline()
    print("---------------------------------------------------")
    print("Pipeline execution complete.")
