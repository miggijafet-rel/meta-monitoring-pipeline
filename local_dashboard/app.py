import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key
import pandas as pd
import os                 # 1. Add this import
from dotenv import load_dotenv  # 2. Add this import

# 3. Load the keys from your hidden .env file sitting in the root folder
load_dotenv()

# 4. Read the token safely into a variable
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


st.set_page_config(page_title="Meta Status Dashboard", page_icon="📊", layout="wide")

st.title("📊 Meta Services Status Dashboard (Serverless Backend)")
st.caption("Data source: AWS DynamoDB populated by EventBridge & Lambda Probers. Click headers to visit login pages.")
st.markdown("---")

# Initialize DynamoDB Client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ServiceStatusLogs')

# We map the database partition keys to their actual user-facing login URLs
SERVICES_MAP = {
    "Facebook-Login": "https://www.facebook.com/login/",
    "Messenger-Login": "https://www.messenger.com/login/",
    "Instagram-Login": "https://www.instagram.com/accounts/login/"
}

cols = st.columns(len(SERVICES_MAP))

for col, (service_db_name, url) in zip(cols, SERVICES_MAP.items()):
    with col:
        # Query last 20 execution data points for charts from DynamoDB
        response = table.query(
            KeyConditionExpression=Key('ServiceName').eq(service_db_name),
            ScanIndexForward=False, # Newest items first
            Limit=20
        )
        items = response.get('Items', [])
        
        if items:
            latest = items[0]
            status = latest['Status']
            latency = float(latest['LatencyMs'])
            code = latest['ResponseCode']
            
            # Using Markdown syntax [Text](URL) to make headers clickable links
            clickable_header = f"### [{service_db_name}]({url})"
            
            # Status Indicator Card with hyperlinks
            if status == "Healthy":
                st.success(clickable_header)
                st.metric(label="Current Latency", value=f"{latency} ms", delta=f"HTTP {code}")
            elif status == "Degraded":
                st.warning(clickable_header)
                st.metric(label="Current Latency", value=f"{latency} ms", delta=f"HTTP {code} - Degraded", delta_color="off")
            else:
                st.error(clickable_header)
                st.metric(label="Current Status", value="DOWN", delta=f"Code: {code}", delta_color="inverse")
                
            # Render historical latency line graph
            df = pd.DataFrame(items)
            df['LatencyMs'] = df['LatencyMs'].astype(float)
            df = df.iloc[::-1] # Flip chronological order for plotting
            
            st.write("**Latency Trend (Last 20 Probes)**")
            st.line_chart(df, x='Timestamp', y='LatencyMs')
        else:
            st.info(f"### [{service_db_name}]({url})\nNo data found in DynamoDB.")

st.markdown("---")
if st.button("🔄 Refresh Dashboard"):
    st.rerun()

st.markdown("---")
st.write("🛠️ **SRE Admin Tools**")

# Replace this with your actual webhook URL for local testing
TEST_DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

if st.button("🚨 Trigger Test Fire Alert"):
    import urllib3
    import json
    from datetime import datetime
    
    http = urllib3.PoolManager()
    payload = {
        "content": "🚨 **SRE ALERT:** Synthetic Test Event Triggered!",
        "embeds": [{
            "title": "Incident Details: Test-Pipeline-Channel",
            "color": 15158332,
            "fields": [
                {"name": "Status", "value": "Testing Connection", "inline": True},
                {"name": "Details/Error", "value": "Manual pipeline validation smoke test from local dashboard.", "inline": True},
                {"name": "Timestamp (UTC)", "value": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
            ]
        }]
    }
    try:
        encoded_data = json.dumps(payload).encode('utf-8')
        res = http.request('POST', TEST_DISCORD_WEBHOOK, body=encoded_data, headers={'Content-Type': 'application/json'})
        if res.status < 300:
            st.toast("Alert fired successfully to Discord!", icon="🔥")
        else:
            st.error(f"Failed to fire alert. HTTP Status: {res.status}")
    except Exception as e:
        st.error(f"Error firing webhook: {e}")