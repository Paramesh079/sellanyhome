import pandas as pd
import requests
import json
import glob
import os
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
# Change this to match the model you have downloaded in Ollama (e.g., 'llama3', 'mistral', 'phi3')
OLLAMA_MODEL = 'qwen2.5vl:7b' 
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# 1. Automatically find the most recently saved Anomalies CSV
csv_files = glob.glob('anomalous_transactions_*.csv')
if not csv_files:
    print("❌ No anomalous transactions CSV found!")
else:
    # Get the newest file
    latest_csv = max(csv_files, key=os.path.getctime)
    print(f"📂 Loading latest anomalies from: {latest_csv}\n")
    
    anomalies = pd.read_csv(latest_csv)
    
    # We will use DuckDuckGo to search the web
    ddgs = DDGS()
    
    # 2. Loop through each anomaly and investigate!
    for index, row in anomalies.iterrows():
        building = row['building_project']
        sub_loc = row['sub_location']
        event_date = pd.to_datetime(row['date'])
        anomaly_type = row.get('Anomaly_Type', 'SUDDEN MOVEMENT')
        pct_change = row.get('Percent_Change_From_Prev', 'Unknown')
        
        print("=" * 80)
        print(f"🔎 INVESTIGATING: {building} in {sub_loc} ({anomaly_type} of {pct_change}%)")
        print("=" * 80)
        print(f"Step 1: Searching the web for '{building} Dubai'...")
        
        # Create a targeted search query
        search_query = f"{building} {sub_loc} Dubai masterplan handover completion news property"
        
        try:
            # Fetch the top 3 search results from the web
            search_results = list(ddgs.text(search_query, max_results=3))
            
            # Combine the snippets into a single text block for the LLM to read
            web_context = ""
            for i, result in enumerate(search_results):
                web_context += f"Result {i+1}: {result['body']}\n"
                
        except Exception as e:
             web_context = "Web search failed or was blocked."
             print(f"  -> Search error: {e}")

        if not web_context.strip():
             web_context = "No relevant news found on the web."
             
        # Step 3: Ask your Local LLM to analyze the situation!
        print(f"Step 2: Asking Local LLM ({OLLAMA_MODEL}) to analyze the web data...\n")
        
        prompt = f"""
        You are a seasoned Dubai Real Estate Analyst. 
        A property in the building "{building}" located in "{sub_loc}" experienced a massive {anomaly_type} in price of {pct_change}% around {event_date.strftime('%B %Y')}.
        
        Here is the latest information I found on the web about this building:
        {web_context}
        
        Based ONLY on the web information provided above and your general knowledge of Dubai real estate (like the massive price jump between off-plan and ready properties), write a short, 3-sentence explanation of WHY this specific price {anomaly_type} likely occurred. Be direct and avoid fluff.
        """
        
        llm_payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            # Send the request to your local Ollama instance
            response = requests.post(OLLAMA_API_URL, json=llm_payload)
            if response.status_code == 200:
                answer = response.json().get('response', '')
                print(f"🤖 LOCAL AI VERDICT:\n{answer.strip()}\n")
            else:
                print(f"❌ Local LLM Error. Is Ollama running? (Status Code: {response.status_code})")
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Could not connect to Local LLM. Please make sure Ollama is running on your machine (http://localhost:11434).")
            break # Stop if Ollama is not running at all
            
        print("\n")
