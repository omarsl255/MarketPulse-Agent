import os
import uuid
from datetime import datetime
from schema import CompetitorEvent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from typing import Optional

def extract_events_from_text(text: str, source_url: str) -> Optional[CompetitorEvent]:
    """Uses LLM to extract a strategic event from raw text."""
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY environment variable not set. Extraction will fail.")
        return None
        
    try:
        parser = PydanticOutputParser(pydantic_object=CompetitorEvent)
        
        template = """
        You are a competitive intelligence agent working for ABB. Your job is to analyze the following web page content 
        from a competitor (e.g., Siemens). 
        Your focus is specifically on finding evidence of: "Developer API & Subdomain Evolution".

        Look for things like:
        - New API endpoints or SDKs
        - Developer portal updates
        - Ghost subdomains or new technical documentation
        - Signals of SaaS or Software-centric ecosystems

        Extract any meaningful strategic event into a SINGLE structured JSON object (do NOT output an array). 
        If no meaningful strategic event is found, highlight any web changes you see, but assign a low confidence score.

        Content to analyze:
        {content}

        Source URL:
        {source_url}

        Current Date:
        {current_date}

        {format_instructions}
        """

        prompt = PromptTemplate(
            template=template,
            input_variables=["content", "source_url", "current_date"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        # Initialize the model (using a fast model for the prototype)
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        
        # Create chain
        chain = prompt | model | parser
        
        # Run extraction
        print("Analyzing content to extract events...")
        event = chain.invoke({
            "content": text[:15000],  # truncate to avoid context limits
            "source_url": source_url,
            "current_date": datetime.now().isoformat()
        })
        
        # Ensure event_id is set
        if not event.event_id:
            event.event_id = str(uuid.uuid4())
            
        return event
    except Exception as e:
        print(f"Extraction failed: {e}")
        return None

if __name__ == "__main__":
    test_text = "Siemens today announced version 2.0 of the Xcelerator Developer API, featuring new endpoints for Edge Device Management and cloud-to-edge deployment synchronization."
    print("Testing extraction...")
    # NOTE: Requires GOOGLE_API_KEY to run
    # result = extract_events_from_text(test_text, "https://developer.siemens.com/news")
    # print(result)
