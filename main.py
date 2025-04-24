import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Google Drive API credentials
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SERVICE_ACCOUNT_FILE = 'credentials.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

drive_service = build('drive', 'v3', credentials=credentials)

# Telegram Bot Token
BOT_TOKEN = '7891601923:AAEDbZIyK5xIfy8a46-gdz73moKS7CgeUww'

# Helper: List folders/files in a given folder ID
def list_drive_items(folder_id):
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Use your Drive's main folder ID or 'root'
    root_id = '1eofoRbraOL4W1uqxTBJlM--ko4_k0aax'  # or use 'root'
    items = list_drive_items(root_id)
    keyboard = [[InlineKeyboardButton(f"📁 {item['name']}", callback_data=item['id'])] for item in items if item['mimeType'] == 'application/vnd.google-apps.folder']
    await update.message.reply_text("📂 Choose a folder:", reply_markup=InlineKeyboardMarkup(keyboard))

# On button click
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
            file_data = drive_service.files().get_media(fileId=file['id']).execute()
            await context.bot.send_document(chat_id=query.message.chat_id, document=file_data, filename=file['name'])

# Main
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("Bot is running...")
    app.run_polling()
