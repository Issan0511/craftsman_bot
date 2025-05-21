from flask import Flask, request, abort
import openai
import os
from dotenv import load_dotenv
import requests # 追加

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# 環境変数から設定を読み込み
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, OPENAI_API_KEY]):
    print("エラー: 必要な環境変数が設定されていません。")
    print("LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, OPENAI_API_KEY を確認してください。")
    exit()

# OpenAI APIキーの設定
openai.api_key = OPENAI_API_KEY

# LINE Messaging APIの設定
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/webhook", methods=['POST'])
def webhook_handler():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Check your channel secret.")
        abort(400)
    except Exception as e:
        app.logger.error(f"Error during webhook handling: {e}")
        abort(500)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_text = event.message.text
    reply_token = event.reply_token
    user_id = event.source.user_id # ユーザーIDを取得

    # ローディングインジケーターを表示
    show_loading_indicator(user_id, seconds=10)

    try:
        # ChatGPT APIに問い合わせ
        # modelは "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview" など状況に応じて選択
        chat_completion = openai.chat.completions.create(
            messages=[
                # {"role": "system", "content": "あなたは親切なアシスタントです。"}, # 必要に応じてシステムプロンプトを設定
                {"role": "user", "content": user_text}
            ],
            model="gpt-3.5-turbo",
            # max_tokens=1000, # 必要に応じて最大トークン数を調整
            # temperature=0.7, # 応答の多様性を調整 (0.0-2.0)
        )
        gpt_response = chat_completion.choices[0].message.content.strip()

    except openai.APIError as e:
        app.logger.error(f"OpenAI API Error: {e}")
        gpt_response = "AIとの通信で問題が発生しました。しばらくしてから再度お試しください。"
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        gpt_response = "申し訳ありません、エラーが発生しました。"

    # LINEに返信
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=gpt_response)]
            )
        )

# ローディング表示用の関数
def show_loading_indicator(user_id, seconds=10):
    headers = {
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        'chatId': user_id,
        'loadingSeconds': seconds
    }
    response = requests.post('https://api.line.me/v2/bot/chat/loading/start', headers=headers, json=data)
    if response.status_code == 202:
        app.logger.info(f"Sent loading indicator to {user_id}")
    else:
        app.logger.error(f"Failed to send loading indicator to {user_id}: {response.text}")

if __name__ == "__main__":
    # .envファイルを作成し、そこにキーを記述してください
    # LINE_CHANNEL_ACCESS_TOKEN=あなたのアクセストークン
    # LINE_CHANNEL_SECRET=あなたのチャネルシークレット
    # OPENAI_API_KEY=あなたのOpenAI APIキー
    app.run(port=os.environ.get('PORT', 8080), debug=True)
