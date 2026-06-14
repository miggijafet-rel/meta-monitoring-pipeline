import json
import time
import urllib3
import boto3
from datetime import datetime

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ServiceStatusLogs')

# TODO: Replace this with your actual Discord Webhook URL string
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

SERVICES = {
    "Facebook-Login": "https://www.facebook.com/login/",
    "Messenger-Login": "https://www.messenger.com/login/",
    "Instagram-Login": "https://www.instagram.com/accounts/login/"
}

def send_discord_alert(service_name, status, details):
    """Sends a formatted alert message to your Discord channel."""
    http = urllib3.PoolManager()
    payload = {
        "content": f"🚨 **SRE ALERT:** {service_name} status is **{status.upper()}**!",
        "embeds": [{
            "title": f"Incident Details: {service_name}",
            "color": 15158332, # Red color block
            "fields": [
                {"name": "Status", "value": status, "inline": True},
                {"name": "Details/Error", "value": str(details), "inline": True},
                {"name": "Timestamp (UTC)", "value": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
            ]
        }]
    }
    
    try:
        encoded_data = json.dumps(payload).encode('utf-8')
        http.request(
            'POST', 
            DISCORD_WEBHOOK_URL, 
            body=encoded_data, 
            headers={'Content-Type': 'application/json'}
        )
    except Exception as e:
        print(f"Failed to send alert to Discord: {e}")

def lambda_handler(event, context):
    http = urllib3.PoolManager(timeout=5.0)
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    for service_name, url in SERVICES.items():
        try:
            start_time = time.time()
            response = http.request('GET', url, headers={"User-Agent": "AWS-Lambda-SRE-Probe"})
            latency = round((time.time() - start_time) * 1000, 2)
            
            if response.status < 400:
                status = "Healthy"
                # SRE Latency SLA breach check (Alert if page response takes > 1.5 seconds)
                if latency > 1500:
                    send_discord_alert(service_name, "Degraded Latency", f"Latency spikes to {latency}ms")
            else:
                status = "Degraded"
                send_discord_alert(service_name, "Degraded", f"HTTP Status Code: {response.status}")
                
            response_code = response.status
            
        except Exception as e:
            status = "Down"
            latency = 0.0
            response_code = "TIMEOUT_OR_CONNECTION_ERROR"
            send_discord_alert(service_name, "Down", str(e))
            
        # Write metrics to DynamoDB table
        table.put_item(
            Item={
                'ServiceName': service_name,
                'Timestamp': timestamp,
                'Status': status,
                'LatencyMs': str(latency),
                'ResponseCode': str(response_code)
            }
        )
        
    return {
        'statusCode': 200,
        'body': json.dumps('Metrics processed and database updated.')
    }