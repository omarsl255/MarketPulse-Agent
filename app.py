import streamlit as st
import pandas as pd
from db import get_all_events

st.set_page_config(page_title="Competitor Radar", layout="wide")

st.title("📡 Early-Warning Intelligence Radar")
st.markdown("Monitoring external signals (Developer APIs, Subdomains, etc.) to detect strategic shifts.")

st.sidebar.header("Agent Controls")
st.sidebar.markdown(
    "To run the extraction pipeline with live data, execute:\\\n`python main.py` in your terminal."
)
competitor_filter = st.sidebar.selectbox("Filter by Competitor", ["All", "Siemens", "Schneider", "Rockwell"])

# Fetch data from SQLite
events_raw = get_all_events()

if not events_raw:
    st.info("No intelligence events found. Run `python main.py` to collect data.")
else:
    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(events_raw)
    
    if competitor_filter != "All":
        df = df[df['competitor'].str.contains(competitor_filter, case=False, na=False)]
        
    st.subheader(f"Detected Strategic Events ({len(df)})")
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Signals", len(df))
    col2.metric("High Confidence Signals", len(df[df['confidence_score'] > 0.7]))
    col3.metric("Monitored Targets", len(df['source_url'].unique()))
    
    st.markdown("---")
    
    # Display the feed
    for _, row in df.iterrows():
        with st.container():
            col_icon, col_content = st.columns([1, 11])
            with col_icon:
                if row['confidence_score'] > 0.8:
                    st.error("🚨 HIGH")
                elif row['confidence_score'] > 0.5:
                    st.warning("⚠️ MED")
                else:
                    st.info("ℹ️ LOW")
            
            with col_content:
                st.markdown(f"### {row['title']}")
                st.caption(f"**Competitor:** {row['competitor']} | **Type:** {row['event_type']} | **Detected:** {row['date_detected'][:10]} | [Source Link]({row['source_url']})")
                st.markdown(f"**What happened:** {row['description']}")
                st.markdown(f"**Strategic Implication for ABB:** _{row['strategic_implication']}_")
                
                with st.expander("Show Details"):
                    st.json({
                        "event_id": row['event_id'],
                        "confidence_score": row['confidence_score']
                    })
            st.markdown("---")
