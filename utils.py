import os, httpx, asyncio, hmac, hashlib, base64
from openai import AsyncOpenAI
from linebot.v3.messaging import (
    ApiClient, Configuration, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage
)
from linebot.v3.messaging.exceptions import ApiException
from dotenv import load_dotenv
import collections # collections をインポート

load_dotenv()

client = AsyncOpenAI()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_HISTORY_LENGTH = 5  # 保存する履歴の最大数
chat_histories = collections.defaultdict(lambda: collections.deque(maxlen=MAX_HISTORY_LENGTH)) # チャット履歴を保存する辞書
system_prompts = collections.defaultdict(lambda: "")  # ユーザーごとのシステムプロンプト

line_access_token = os.getenv("LINE_ACCESS_TOKEN")
if line_access_token is None:
    raise ValueError(
        "The LINE_ACCESS_TOKEN environment variable is not set. "
        "Please set this variable to your LINE channel access token."
    )
cfg = Configuration(access_token=line_access_token)

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
async def call_gpt_stream(user_id: str, user_msg: str) -> str:
    """OpenAI ChatCompletion をストリーム受信して結合（システムプロンプト対応）"""
    chunks = []
    current_history = list(chat_histories[user_id])
    system_prompt = system_prompts[user_id]
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages += current_history + [{"role": "user", "content": user_msg}]

    stream = await client.chat.completions.create(
        model=OPENAI_MODEL,
        stream=True,
        messages=messages, # 履歴を考慮したメッセージリスト
        max_tokens=1024,
        temperature=0.8,
    )
    async for part in stream:
        delta = part.choices[0].delta
        if delta and delta.content:
            chunks.append(delta.content) # 修正: delta.content を直接追加
            
    bot_response = "".join(chunks)
    # ユーザーのメッセージとボットの応答を履歴に追加
    chat_histories[user_id].append({"role": "user", "content": user_msg})
    chat_histories[user_id].append({"role": "assistant", "content": bot_response})
    return bot_response

async def call_gpt_block(user_id: str, user_msg: str) -> str:
    """OpenAI ChatCompletion をブロッキングで受信（システムプロンプト対応）"""
    current_history = list(chat_histories[user_id])
    system_prompt = system_prompts[user_id]
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages += current_history + [{"role": "user", "content": user_msg}]

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.8,
    )
    bot_response = response.choices[0].message.content
    # ユーザーのメッセージとボットの応答を履歴に追加
    chat_histories[user_id].append({"role": "user", "content": user_msg})
    chat_histories[user_id].append({"role": "assistant", "content": bot_response})
    return bot_response

# -- 署名 -------------------------------------------------------------
import hashlib # hashlib をインポート
import hmac    # hmac をインポート
import base64  # base64 をインポート
def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    mac = hmac.new(channel_secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(mac), signature.encode())
