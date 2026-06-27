import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from mlflow.deployments import get_deploy_client

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])
client = get_deploy_client("databricks")

@app.event("app_mention")
def handle(event, say):
    text = event["text"].split(">", 1)[-1].strip() # text looks like <@U09ABC123> how is ...
    r = client.predict(
        endpoint="agents_suppliers_catalog-gold-supplier_agent",
        inputs={
            "messages": [{"role": "user", "content": text}]
        }
    )
    say(r["messages"][-1]["content"])

SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()

@app.event("message")
def handle_dm(event, say):
    if event.get("channel_type") != "im" or event.get("bot_id"):
        return
    text = event["text"].strip()
    r = client.predict(
        endpoint="agents_suppliers_catalog-gold-supplier_agent",
        inputs={
            "messages": [{"role": "user", "content": text}]
        }
    )
    say(r["messages"][-1]["content"])
