import asyncio
import json
import os
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- CONFIGURATION ---
API_ID = 21862154
API_HASH = "af2a54cdf05008758eca7b577195804f"
BOT_TOKEN = "8446057086:AAFJWeh-sKiVxB_S82UUceogqKBCsjeYcSw"
CHANNEL_ID = -1003681497751
LINK_URL = "https://t.me/+4PtFW22RdZ0yYTA9"  # The link users go to when clicking the caption

# --- ANALYTICS FILE SETUP ---
STATS_FILE = "stats.json"

# Global dictionary to store search results for pagination
# Format: {user_id: [list_of_movie_buttons]}
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
    
    # Load existing
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
        except:
            pass # If file is corrupt, start fresh

    # Update
    if action == "search":
        data["total_searches"] += 1
    elif action == "download":
        data["files_sent"] += 1
        
    # Save
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
        if status_msg: await status_msg.edit("❌ Session expired. Search again.")
        return

    results = USER_SESSIONS[user_id]
    total_results = len(results)
    items_per_page = 15
    total_pages = (total_results + items_per_page - 1) // items_per_page

    # Slice the list for the current page
    start = (page - 1) * items_per_page
    end = start + items_per_page
    current_items = results[start:end]

    # Build Buttons
    keyboard_rows = []
    for movie in current_items:
        # Button Text: "Movie Name [1.2 GB]"
        btn_text = f"[{get_readable_size(movie['size'])}] {movie['name']}"
        keyboard_rows.append([InlineKeyboardButton(btn_text, callback_data=f"dl_{movie['id']}")])

    # Navigation Buttons
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


# --- 1. SEARCH HANDLER ---
@app.on_message(filters.private & filters.text)
async def search_handler(client, message):
    user_query = message.text.strip().lower()
    words = user_query.split()
    if not words: return

    # Track Analytics
    update_stats("search")

    status_msg = await message.reply("🔍 Searching Database...")
    
    found_movies = []      
    seen_ids = set() 
    
    # Search Logic (Iterative)
    for i in range(len(words), 0, -1):
        current_search = words[:i]
        
        for movie in MOVIE_DB:
            if movie['id'] in seen_ids: continue
            
            content_to_check = (movie['name'].lower() + " " + movie['caption'])
            
            # Check if ALL words match
            if all(word in content_to_check for word in current_search):
                found_movies.append(movie)
                seen_ids.add(movie['id'])
    
    if not found_movies:
        await status_msg.edit(f"❌ No results found for '{message.text}'")
        return

    # Save results to session for pagination
    USER_SESSIONS[message.from_user.id] = found_movies

    # Show Page 1
    await show_page(client, message.chat.id, message.from_user.id, page=1, status_msg=status_msg)


# --- 2. PAGINATION CALLBACK ---
@app.on_callback_query(filters.regex(r"^page_"))
async def page_callback(client, callback: CallbackQuery):
    page = int(callback.data.split("_")[1])
    await show_page(client, callback.message.chat.id, callback.from_user.id, page=page, status_msg=callback.message)
    await callback.answer()

@app.on_callback_query(filters.regex(r"^ignore"))
async def ignore_callback(client, callback: CallbackQuery):
    await callback.answer("Current Page info")


# --- 3. DOWNLOAD CALLBACK (With Custom Link) ---
@app.on_callback_query(filters.regex(r"^dl_"))
async def send_movie_callback(client, callback: CallbackQuery):
    file_id = int(callback.data.split("_")[1])
    
    # Find movie details from DB
    movie_info = next((m for m in MOVIE_DB if m['id'] == file_id), None)
    
    await callback.answer("Sending file...")
    update_stats("download")
    
    try:
        # Create Custom Caption
        # 1. Name + Size as a clickable link
        # 2. Advice text below
        f_size = get_readable_size(movie_info['size']) if movie_info else ""
        f_name = movie_info['name'] if movie_info else "Movie File"
        
        custom_caption = (
            f"<a href='{LINK_URL}'>{f_name} - {f_size}</a>\n\n"
            f"use mx player in phone and vlc in pc for better experience"
        )

        sent_msg = await client.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=file_id,
            caption=custom_caption,
            parse_mode=enums.ParseMode.HTML # Important for the link to work
        )
        
        # Auto Delete
        await asyncio.sleep(120)
        await sent_msg.delete()
        
    except Exception as e:
        await callback.message.reply(f"Error: {e}")

print("Bot Started...")
app.run()
