from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from utils import (
    verify_signature, show_loading, call_gpt_stream, reply_or_push, os
)

app = FastAPI()
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

@app.post("/webhook")
async def webhook(req: Request, bg: BackgroundTasks):
    sig = req.headers.get("x-line-signature")
    body = await req.body()
    if not CHANNEL_SECRET or not sig:
        raise HTTPException(status_code=400, detail="Channel secret or signature not found")
    if not verify_signature(CHANNEL_SECRET, body, sig):
        raise HTTPException(status_code=400, detail="Bad signature")
    event = (await req.json())["events"][0]

    # ── テキストメッセージのみ対象 ──────────────────────────────
    if event["type"] == "message" and event["message"]["type"] == "text":
        uid   = event["source"]["userId"]
        token = event["replyToken"]
        text  = event["message"]["text"]

        # 1) ローディング開始（非同期）
        bg.add_task(show_loading, uid, 60)

        # 2) GPT 呼び出し & 返信 / プッシュ
        async def async_flow():
            answer = await call_gpt_stream(text)
            await reply_or_push(uid, token, answer)

        bg.add_task(async_flow)

    return "ok"
