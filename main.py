from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from utils import (
    verify_signature,
    show_loading,
    call_gpt_block,
    reply_or_push,
    log_to_gas,
    os,
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

        message_id = event["message"]["id"]

        # 2) GPT 呼び出し & 返信 / プッシュ & GAS ログ
        async def async_flow():
            answer = await call_gpt_block(uid, text)  # uid を call_gpt_block に渡す
            await reply_or_push(uid, token, answer)
            await log_to_gas(message_id, text, answer)

        bg.add_task(async_flow)

    return "ok"
