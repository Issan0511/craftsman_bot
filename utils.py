import os, httpx, asyncio, hmac, hashlib, base64
from openai import AsyncOpenAI
from linebot.v3.messaging import (
    ApiClient, Configuration, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage
)
from linebot.v3.messaging.exceptions import ApiException
from dotenv import load_dotenv
import collections # collections をインポート
import glob # glob をインポート

load_dotenv()

client = AsyncOpenAI()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
MAX_HISTORY_LENGTH = 5  # 保存する履歴の最大数
chat_histories = collections.defaultdict(lambda: collections.deque(maxlen=MAX_HISTORY_LENGTH)) # チャット履歴を保存する辞書
system_prompts = collections.defaultdict(lambda: "")  # ユーザーごとのシステムプロンプト

def get_access_token_key() -> str:
    """現在のアクセストークンに基づいてキーを生成"""
    token = os.getenv("LINE_ACCESS_TOKEN", "")
    # トークンの最後の10文字をキーとして使用（デバッグ用）
    return token[-10:] if len(token) >= 10 else "default"

def load_system_prompt_for_token() -> str:
    """アクセストークンに応じたシステムプロンプトを読み込み"""
    token_key = get_access_token_key()
    prompt_dir = f"systemprompts/{token_key}"
    
    # トークン用のディレクトリが存在しない場合はdefaultを使用
    if not os.path.exists(prompt_dir):
        prompt_dir = "systemprompts/default"
    
    system_prompt = ""
    
    try:
        # instructions.mdを読み込み
        instructions_path = os.path.join(prompt_dir, "instructions.md")
        if os.path.exists(instructions_path):
            with open(instructions_path, 'r', encoding='utf-8') as f:
                system_prompt += f.read() + "\n\n"
        
        # materials.mdを読み込み
        materials_path = os.path.join(prompt_dir, "materials.md")
        if os.path.exists(materials_path):
            with open(materials_path, 'r', encoding='utf-8') as f:
                system_prompt += "## 技術資料\n" + f.read()
                
    except Exception as e:
        print(f"システムプロンプト読み込みエラー: {e}")
        return "あなたは親切で知識豊富なアシスタントです。"
    
    return system_prompt.strip() if system_prompt.strip() else "あなたは親切で知識豊富なアシスタントです。"

# グローバルなシステムプロンプトを初期化
GLOBAL_SYSTEM_PROMPT = load_system_prompt_for_token()

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

# -- GAS ---------------------------------------------------------------
async def log_to_gas(message_id: str, question: str, response: str, sheet_name: str | None = None):
    """Send chat logs to Google Apps Script if GAS_LOG_URL is set."""
    gas_url = os.getenv("GAS_LOG_URL")
    if not gas_url:
        return

    payload = {
        "messageId": message_id,
        "question": question,
        "response": response,
    }
    if sheet_name:
        payload["sheetName"] = sheet_name

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(gas_url, json=payload)
    except Exception as e:
        # ログ送信失敗時はエラーメッセージを表示するが処理は継続
        print(f"GAS logging failed: {e}")

# -- GPT --------------------------------------------------------------
async def call_gpt_stream(user_id: str, user_msg: str) -> str:
    """OpenAI ChatCompletion をストリーム受信して結合（システムプロンプト対応）"""
    chunks = []
    current_history = list(chat_histories[user_id])
    # グローバルなシステムプロンプトを使用
    messages = [{"role": "system", "content": GLOBAL_SYSTEM_PROMPT}]
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
    # グローバルなシステムプロンプトを使用
    messages = [{"role": "system", "content": GLOBAL_SYSTEM_PROMPT}]
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
