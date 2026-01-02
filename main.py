import asyncio
import json
import os
import urllib.parse
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- CONFIGURATION ---
API_ID = 21862154
API_HASH = "af2a54cdf05008758eca7b577195804f"
BOT_TOKEN = "8446057086:AAFJWeh-sKiVxB_S82UUceogqKBCsjeYcSw"
CHANNEL_ID = -1003681497751
CHANNEL_LINK = "https://t.me/+4PtFW22RdZ0yYTA9"

# --- ANALYTICS FILE SETUP ---
STATS_FILE = "stats.json"

# Global dictionary to store search results for pagination
USER_SESSIONS = {}

# --- LOAD DATABASE ---
if os.path.exists("movies.json"):
    with open("movies.json", "r", encoding="utf-8") as f:
        MOVIE_DB = json.load(f)
    print(f"✅ Database Loaded: {len(MOVIE_DB)} movies.")
else:
    print("❌ ERROR: 'movies.json' not found. Run indexer.py first!")
    MOVIE_DB = []

app = Client("movie_search_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HELPER: UPDATE ANALYTICS ---
def update_stats(action):
    """Updates the stats.json file for 'search' or 'download'."""
    data = {"total_searches": 0, "files_sent": 0}
    
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
        except:
            pass

    if action == "search":
        data["total_searches"] += 1
    elif action == "download":
        data["files_sent"] += 1
        
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- HELPER: FORMAT SIZE ---
def get_readable_size(size_in_bytes):
    """Converts bytes to MB or GB"""
    if size_in_bytes >= 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.2f} GB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.2f} MB"

# --- HELPER: SHOW PAGE ---
async def show_page(client, chat_id, user_id, page=1, status_msg=None):
    """Displays the specific page of results."""
    if user_id not in USER_SESSIONS:
        if status_msg: 
            await status_msg.edit("❌ Session expired. Search again.")
        return

    results = USER_SESSIONS[user_id]
    total_results = len(results)
    items_per_page = 15
    total_pages = (total_results + items_per_page - 1) // items_per_page

    start = (page - 1) * items_per_page
    end = start + items_per_page
    current_items = results[start:end]

    keyboard_rows = []
    for movie in current_items:
        btn_text = f"[{get_readable_size(movie['size'])}] {movie['name']}"
        keyboard_rows.append([InlineKeyboardButton(btn_text, callback_data=f"dl_{movie['id']}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))

    if nav_buttons:
        keyboard_rows.append(nav_buttons)

    markup = InlineKeyboardMarkup(keyboard_rows)
    text = f"Found **{total_results}** files.\nPage **{page}** of **{total_pages}**"

    if status_msg:
        await status_msg.edit(text, reply_markup=markup)
    else:
        await client.send_message(chat_id, text, reply_markup=markup)


# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    guide_text = """
👋 **Welcome to Movie Search Bot!**

📌 **How to Use / Kaise Use Karein:**

1️⃣ **Check Spelling First / Pehle Spelling Check Karein**
   • Verify correct movie name on Google
   • Google par sahi movie naam check karein

2️⃣ **Search Movies / Movies Search Karein**
   • Just type the movie name
   • Bas movie ka naam type karein
   • Example: Avengers

3️⃣ **Select & Download / Select Aur Download Karein**
   • Click on the movie from results
   • Results mein se movie par click karein
   • File will be sent instantly
   • File turant bhej di jayegi

💡 **Tips:**
   • Use correct spelling for better results
   • Sahi spelling use karein behtar results ke liye
   
🎬 **For Best Playback / Best Playback Ke Liye:**
   • Phone: Use MX Player
   • PC: Use VLC Media Player

❓ **Need Help? / Madad Chahiye?**
Just send the movie name and start searching!
Bas movie ka naam bhejein aur search shuru karein!
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel / Channel Join Karein", url=CHANNEL_LINK)]
    ])
    
    await message.reply(guide_text, reply_markup=keyboard)


# --- PRIVATE SEARCH HANDLER ---
@app.on_message(filters.private & filters.text & ~filters.command(["start", "movie"]))
async def search_handler(client, message):
    user_query = message.text.strip().lower()
    words = user_query.split()
    if not words: 
        return

    update_stats("search")
    status_msg = await message.reply("🔍 Searching Database...")
    
    found_movies = []      
    seen_ids = set() 
    
    for i in range(len(words), 0, -1):
        current_search = words[:i]
        
        for movie in MOVIE_DB:
            if movie['id'] in seen_ids: 
                continue
            
            content_to_check = (movie['name'].lower() + " " + movie['caption'])
            
            if all(word in content_to_check for word in current_search):
                found_movies.append(movie)
                seen_ids.add(movie['id'])
    
    if not found_movies:
        # Create Google search link
        google_query = urllib.parse.quote(f"correct spelling of {message.text} movie")
        google_link = f"https://www.google.com/search?q={google_query}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Check Spelling on Google / Google Par Spelling Check Karein", url=google_link)]
        ])
        
        no_result_text = f"❌ **No results found for '{message.text}'**\n\n"
        no_result_text += "Please check the spelling on Google.\n"
        no_result_text += "Kripya Google par spelling check karein."
        
        await status_msg.edit(no_result_text, reply_markup=keyboard)
        return

    USER_SESSIONS[message.from_user.id] = found_movies
    await show_page(client, message.chat.id, message.from_user.id, page=1, status_msg=status_msg)


# --- GROUP MOVIE COMMAND ---
@app.on_message(filters.group & filters.command("movie"))
async def group_movie_command(client, message):
    if len(message.command) < 2:
        await message.reply("Please provide a movie name.\nKripya movie ka naam dijiye.\n\nExample: `/movie Avengers`")
        return
    
    user_query = " ".join(message.command[1:]).strip().lower()
    words = user_query.split()
    
    update_stats("search")
    status_msg = await message.reply("🔍 Searching...")
    
    found_movies = []      
    seen_ids = set() 
    
    for i in range(len(words), 0, -1):
        current_search = words[:i]
        
        for movie in MOVIE_DB:
            if movie['id'] in seen_ids: 
                continue
            
            content_to_check = (movie['name'].lower() + " " + movie['caption'])
            
            if all(word in content_to_check for word in current_search):
                found_movies.append(movie)
                seen_ids.add(movie['id'])
    
    if not found_movies:
        google_query = urllib.parse.quote(f"correct spelling of {user_query} movie")
        google_link = f"https://www.google.com/search?q={google_query}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Check Spelling on Google", url=google_link)]
        ])
        
        await status_msg.edit(f"❌ No results found. Please check spelling.", reply_markup=keyboard)
        return
    
    # Send first result in groups
    movie_info = found_movies[0]
    update_stats("download")
    
    try:
        f_size = get_readable_size(movie_info['size'])
        f_name = movie_info['name']
        
        custom_caption = (
            f"<b>{f_name}</b>\n"
            f"<b>Size:</b> {f_size}\n\n"
            f"⚠️ <b>File will be deleted in 1 minute. Forward it now!</b>\n"
            f"⚠️ <b>File 1 minute mein delete ho jayegi. Abhi forward karein !</b>\n\n"
            f"💡 Use MX Player (phone) / VLC (PC) for best experience"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]
        ])

        sent_msg = await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=movie_info['id'],
            caption=custom_caption,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
        
        await status_msg.delete()
        
        # Auto delete after 1 minute in groups
        await asyncio.sleep(60)
        await sent_msg.delete()
        
    except Exception as e:
        await message.reply(f"Error: {e}")


# --- PAGINATION CALLBACK ---
@app.on_callback_query(filters.regex(r"^page_"))
async def page_callback(client, callback: CallbackQuery):
    page = int(callback.data.split("_")[1])
    await show_page(client, callback.message.chat.id, callback.from_user.id, page=page, status_msg=callback.message)
    await callback.answer()


@app.on_callback_query(filters.regex(r"^ignore"))
async def ignore_callback(client, callback: CallbackQuery):
    await callback.answer("Current Page info")


# --- DOWNLOAD CALLBACK (Private Only) ---
@app.on_callback_query(filters.regex(r"^dl_"))
async def send_movie_callback(client, callback: CallbackQuery):
    file_id = int(callback.data.split("_")[1])
    
    movie_info = next((m for m in MOVIE_DB if m['id'] == file_id), None)
    
    await callback.answer("Sending file...")
    update_stats("download")
    
    try:
        f_size = get_readable_size(movie_info['size']) if movie_info else ""
        f_name = movie_info['name'] if movie_info else "Movie File"
        
        custom_caption = (
            f"<b>{f_name}</b>\n"
            f"<b>Size:</b> {f_size}\n\n"
            f"💡 <b>For Best Experience:</b>\n"
            f"   📱 Phone: Use MX Player\n"
            f"   💻 PC: Use VLC Media Player\n\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]
        ])

        await client.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=file_id,
            caption=custom_caption,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        await callback.message.reply(f"Error: {e}")


print("Bot Started...")
app.run()
