import os
import logging
import io
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes, AIORateLimiter
)
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIG ---
BOT_TOKEN = "7891601923:AAEDbZIyK5xIfy8a46-gdz73moKS7CgeUww"
ROOT_FOLDER_ID = '1eofoRbraOL4W1uqxTBJlM--ko4_k0aax'
SERVICE_ACCOUNT_FILE = 'credentials.json'

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Google Drive API setup ---
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)

def list_drive_items(folder_id):
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🚀 /start command triggered")
    items = list_drive_items(ROOT_FOLDER_ID)
    keyboard = [
        [InlineKeyboardButton(f"📁 {item['name']}", callback_data=item['id'])]
        for item in items if item['mimeType'] == 'application/vnd.google-apps.folder'
    ]
    await update.message.reply_text("📂 Choose a folder:", reply_markup=InlineKeyboardMarkup(keyboard))

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

# --- Main run ---
async def main():
    app = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    logger.info("🤖 Bot is starting with polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == '__main__':
    asyncio.run(main())
