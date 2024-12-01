import os
import requests
from PIL import Image
from io import BytesIO
from telegram import Update
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
IMAGE_DIR = os.getenv("IMAGE_DIR", "./images")
BASE_URL = os.getenv("BASE_URL", "http://localhost")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables.")

os.makedirs(IMAGE_DIR, exist_ok=True)

app = Flask(__name__)

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Send me a URL of an image, and I'll compress it for you!")

async def handle_url(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    user_id = update.message.chat_id

    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("Invalid URL! Please send a valid URL.")
        return

    try:
        response = requests.head(url, allow_redirects=True)
        if response.status_code != 200:
            await update.message.reply_text(f"URL is not accessible! Status code: {response.status_code}")
            return
        content_length = response.headers.get('content-length', 'unknown')
        await update.message.reply_text(f"URL is valid! File size: {content_length} bytes")
    except Exception as e:
        await update.message.reply_text(f"Error validating URL: {e}")
        return

    await update.message.reply_text("Downloading image... Please wait.")
    try:
        file_path = os.path.join(IMAGE_DIR, f"{user_id}_image.jpg")
        download_image(url, file_path)

        compressed_path = os.path.join(IMAGE_DIR, f"{user_id}_compressed.jpg")
        compress_image(file_path, compressed_path)

        await update.message.reply_text("Image compressed successfully!")

        if os.path.getsize(compressed_path) > 50 * 1024 * 1024:
            download_url = f"{BASE_URL}/images/{user_id}_compressed.jpg"
            await update.message.reply_text(
                f"The file is too large to send via Telegram. You can download it from: {download_url}"
            )
        else:
            await update.message.reply_document(document=open(compressed_path, "rb"))
    except Exception as e:
        await update.message.reply_text(f"Error processing image: {e}")

def download_image(url: str, file_path: str):
    response = requests.get(url)
    response.raise_for_status()

    with open(file_path, 'wb') as f:
        f.write(response.content)

def compress_image(input_file: str, output_file: str):
    with Image.open(input_file) as img:
        img = img.convert("RGB")
        img.save(output_file, format="JPEG", quality=80, optimize=True)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    from threading import Thread
    flask_thread = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 5000})
    flask_thread.start()

    application.run_polling()

if __name__ == "__main__":
    main()
