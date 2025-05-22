import os, httpx, openai, asyncio, hmac, hashlib, base64
from linebot.v3.messaging import (
    ApiClient, Configuration, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage
)
from linebot.v3.messaging.exceptions import ApiException
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

cfg = Configuration(access_token=os.getenv("LINE_ACCESS_TOKEN"))

# -- LINE -------------------------------------------------------------
async def show_loading(chat_id: str, seconds: int = 30):
    """ローディングアニメーションを開始（5–60 秒）"""
    seconds = min(max(seconds, 5), 60)
    url = "https://api.line.me/v2/bot/chat/loading/start"
    headers = {"Authorization": f"Bearer {os.getenv('LINE_ACCESS_TOKEN')}"}
    payload = {"chatId": chat_id, "loadingSeconds": seconds}
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(url, headers=headers, json=payload)

async def reply_or_push(user_id: str, reply_token: str, text: str):
    """30 秒以内は reply、それ以降は push に切替え"""
    with ApiClient(cfg) as api_client:
        msg = [TextMessage(text=text)]
        messaging_api = MessagingApi(api_client)
        try:
            messaging_api.reply_message_with_http_info(
                ReplyMessageRequest(reply_token=reply_token, messages=msg)
            )
        except ApiException as e:
            if e.status == 400 and "Invalid reply token" in str(e.body):
                messaging_api.push_message_with_http_info(
                    PushMessageRequest(to=user_id, messages=msg)
                )
            else:
                raise

# -- GPT --------------------------------------------------------------
async def call_gpt_stream(user_msg: str) -> str:
    """OpenAI ChatCompletion をストリーム受信して結合"""
    chunks = []
    stream = await openai.chat.completions.async_create(
        model=OPENAI_MODEL,
        stream=True,
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=1024,
        temperature=0.8,
    )
    async for part in stream:
        delta = part.choices[0].delta
        if delta and delta.content:
            chunks.append(delta.content)
    return "".join(chunks)

# -- 署名 -------------------------------------------------------------
def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    mac = hmac.new(channel_secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(mac), signature.encode())
