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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants (already filled)
BOT_TOKEN = "7891601923:AAEDbZIyK5xIfy8a46-gdz73moKS7CgeUww"
WEBHOOK_URL = "https://amlahtradingbot.onrender.com/7891601923:AAEDbZIyK5xIfy8a46-gdz73moKS7CgeUww"
ROOT_ID = "1eofoRbraOL4W1uqxTBJlM--ko4_k0aax"

# Google Drive setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
credentials = service_account.Credentials.from_service_account_file(
    'credentials.json', scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)

# FastAPI + Telegram setup
app = FastAPI()
application = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

def list_drive_items(folder_id):
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = list_drive_items(ROOT_ID)
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

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))

@app.post(f"/{BOT_TOKEN}")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    await application.initialize()
    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logger.info("✅ Webhook set successfully.")
