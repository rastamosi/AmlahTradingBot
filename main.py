import os
import logging
import io
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes, AIORateLimiter
)
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SERVICE_ACCOUNT_FILE = 'credentials.json'
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)

# FastAPI app
app = FastAPI()

# Telegram app
application = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

def list_drive_items(folder_id):
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🚀 /start received") 
    root_id = '1eofoRbraOL4W1uqxTBJlM--ko4_k0aax'
    items = list_drive_items(root_id)
    keyboard = [
        [InlineKeyboardButton(f"📁 {item['name']}", callback_data=item['id'])]
        for item in items if item['mimeType'] == 'application/vnd.google-apps.folder'
    ]
    await update.message.reply_text("📂 Choose a folder:", reply_markup=InlineKeyboardMarkup(keyboard))

# Folder navigation
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    folder_id = query.data
    items = list_drive_items(folder_id)
    files = [item for item in items if not item['mimeType'].endswith('.folder')]
    folders = [item for item in items if item['mimeType'].endswith('.folder')]

    if folders:
        keyboard = [[InlineKeyboardButton(f"📁 {f['name']}", callback_data=f['id'])] for f in folders]
        await query.edit_message_text("📂 Choose a subfolder:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif files:
        await query.edit_message_text("📄 Sending files...")
        for file in files:
            fh = io.BytesIO()
            request = drive_service.files().get_media(fileId=file['id'])
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            await context.bot.send_document(chat_id=query.message.chat.id, document=fh, filename=file['name'])
    else:
        await query.edit_message_text("🚫 This folder is empty.")

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))

# Telegram webhook handler (route must match token)
@app.post(f"/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    data = await req.json()
    logger.info(f"📩 Incoming update: {data}")  # 👈 Add this
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

# Startup hook: Set webhook
@app.on_event("startup")
async def on_startup():
    logger.info("🌱 Startup initiated")
    try:
        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.bot.set_webhook(url=f"{WEBHOOK_URL}")
        logger.info("✅ Webhook set and bot initialized.")
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")

