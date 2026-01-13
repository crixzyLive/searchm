import asyncio
import json
import os
import urllib.parse
import zipfile  # <--- NEW IMPORT
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- CONFIGURATION ---
API_ID = 21862154
API_HASH = "af2a54cdf05008758eca7b577195804f"
BOT_TOKEN = "8446057086:AAFJWeh-sKiVxB_S82UUceogqKBCsjeYcSw"

# Multiple channels configuration
CHANNELS = [
    {
        "id": -1003681497751,
        "link": "https://t.me/+4PtFW22RdZ0yYTA9",
        "db_file": "movies.json" 
    },
    {
        "id": -1003649132067, 
        "link": "https://t.me/+4PtFW22RdZ0yYTA9", 
        "db_file": "movies2.zip"  # <--- CHANGE THIS TO .zip
    }
]

ADMIN_IDS = [] 

# --- ANALYTICS FILE SETUP ---
STATS_FILE = "stats.json"

# Global dictionary to store search results for pagination
USER_SESSIONS = {}
GROUP_RATE_LIMITS = {}

# --- LOAD DATABASES FROM MULTIPLE CHANNELS ---
MOVIE_DB = []
CHANNEL_MAP = {} 

print("🔄 Loading databases...")

for channel in CHANNELS:
    db_file = channel["db_file"]
    movies = []
    
    try:
        if os.path.exists(db_file):
            # Check if it is a ZIP file
            if db_file.endswith(".zip"):
                print(f"📦 Unzipping and loading {db_file}...")
                with zipfile.ZipFile(db_file, 'r') as z:
                    # We assume the zip contains one json file. We read the first file found.
                    file_in_zip = z.namelist()[0]
                    with z.open(file_in_zip) as f:
                        data = f.read()
                        movies = json.loads(data)
            
            # Check if it is a JSON file
            elif db_file.endswith(".json"):
                with open(db_file, "r", encoding="utf-8") as f:
                    movies = json.load(f)
            
            print(f"✅ Loaded {len(movies)} movies from {db_file}")

            # Add movies to main database
            for movie in movies:
                MOVIE_DB.append(movie)
                CHANNEL_MAP[movie['id']] = {
                    "channel_id": channel["id"],
                    "channel_link": channel["link"]
                }
        else:
            print(f"⚠️ Warning: '{db_file}' not found!")
            
    except Exception as e:
        print(f"❌ Error loading {db_file}: {e}")

if not MOVIE_DB:
    print("❌ ERROR: No movie databases found.")
else:
    print(f"✅ Total Database Loaded: {len(MOVIE_DB)} movies from {len(CHANNELS)} channels.")

app = Client("movie_search_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ... THE REST OF YOUR CODE REMAINS THE SAME ...

# --- HELPER: INITIALIZE STATS ---
def initialize_stats():
    """Create stats file if it doesn't exist"""
    if not os.path.exists(STATS_FILE):
        default_stats = {
            "total_searches": 0,
            "files_sent": 0,
            "total_users": set(),
            "group_searches": 0,
            "private_searches": 0,
            "failed_searches": 0,
            "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(STATS_FILE, "w") as f:
            json.dump(default_stats, f, indent=4, default=str)

# --- HELPER: UPDATE ANALYTICS ---
def update_stats(action, user_id=None, is_group=False):
    """Updates the stats.json file for various actions."""
    initialize_stats()
    
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {
            "total_searches": 0,
            "files_sent": 0,
            "total_users": [],
            "group_searches": 0,
            "private_searches": 0,
            "failed_searches": 0,
            "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    # Ensure total_users is a list
    if not isinstance(data.get("total_users"), list):
        data["total_users"] = []
    
    # Convert to set for operations
    user_set = set(data["total_users"])

    # Update based on action
    if action == "search":
        data["total_searches"] = data.get("total_searches", 0) + 1
        if is_group:
            data["group_searches"] = data.get("group_searches", 0) + 1
        else:
            data["private_searches"] = data.get("private_searches", 0) + 1
    elif action == "download":
        data["files_sent"] = data.get("files_sent", 0) + 1
    elif action == "failed_search":
        data["failed_searches"] = data.get("failed_searches", 0) + 1
    elif action == "user":
        pass  # Just tracking user, no counter update
    
    # Add user to set
    if user_id:
        user_set.add(user_id)
    
    # Convert set back to list for JSON serialization
    data["total_users"] = list(user_set)
    
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- HELPER: GET STATS ---
def get_stats():
    """Retrieve current statistics"""
    initialize_stats()
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
        
        if isinstance(data.get("total_users"), list):
            data["unique_users"] = len(data["total_users"])
        else:
            data["unique_users"] = 0
            
        return data
    except:
        return None

# --- HELPER: FORMAT SIZE ---
def get_readable_size(size_in_bytes):
    """Converts bytes to MB or GB"""
    if size_in_bytes >= 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.2f} GB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.2f} MB"

# --- HELPER: CALCULATE TOTAL SIZE ---
def get_total_database_size():
    """Calculate total size of all movies in database"""
    total_size = sum(movie.get('size', 0) for movie in MOVIE_DB)
    return get_readable_size(total_size)

# --- HELPER: CHECK IF MESSAGE IS COMMAND ---
def is_command(text):
    """Check if the message starts with a slash (/) indicating it's a command"""
    return text.strip().startswith("/")

# --- HELPER: GET GROUP INVITE LINK ---
async def get_group_link(client, chat_id):
    """Get the invite link for a group"""
    try:
        chat = await client.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
        else:
            # Try to get invite link
            try:
                link = await client.export_chat_invite_link(chat_id)
                return link
            except:
                return None
    except:
        return None

# --- HELPER: CHECK GROUP RATE LIMIT ---
def check_group_rate_limit(group_id):
    """Check if group has exceeded rate limit (1 request, 5 files per 20 seconds)"""
    now = datetime.now()
    
    if group_id not in GROUP_RATE_LIMITS:
        GROUP_RATE_LIMITS[group_id] = {
            'last_request': now,
            'file_count': 0,
            'reset_time': now + timedelta(seconds=20)
        }
        return True, 0
    
    limit_data = GROUP_RATE_LIMITS[group_id]
    
    # Reset if 20 seconds have passed
    if now >= limit_data['reset_time']:
        GROUP_RATE_LIMITS[group_id] = {
            'last_request': now,
            'file_count': 0,
            'reset_time': now + timedelta(seconds=20)
        }
        return True, 0
    
    # Check if already had a request in this window
    if limit_data['file_count'] >= 5:
        remaining_time = (limit_data['reset_time'] - now).seconds
        return False, remaining_time
    
    return True, 0

# --- HELPER: UPDATE GROUP RATE LIMIT ---
def update_group_rate_limit(group_id):
    """Increment file count for group"""
    if group_id in GROUP_RATE_LIMITS:
        GROUP_RATE_LIMITS[group_id]['file_count'] += 1

# --- HELPER: GET DEFAULT CHANNEL LINK ---
def get_default_channel_link():
    """Get the first channel link as default"""
    return CHANNELS[0]["link"] if CHANNELS else "#"

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


# --- HELPER: SHOW GROUP RESULTS PAGE ---
async def show_group_page(client, chat_id, user_id, page=1, status_msg=None):
    """Displays the specific page of results for group searches."""
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
        keyboard_rows.append([InlineKeyboardButton(btn_text, callback_data=f"grp_dl_{movie['id']}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"grp_page_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"grp_page_{page+1}"))

    if nav_buttons:
        keyboard_rows.append(nav_buttons)

    markup = InlineKeyboardMarkup(keyboard_rows)
    text = f"Found **{total_results}** files.\nPage **{page}** of **{total_pages}**\n\nSelect a movie to download:"

    if status_msg:
        await status_msg.edit(text, reply_markup=markup)
    else:
        await client.send_message(chat_id, text, reply_markup=markup)


# --- START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    update_stats("user", user_id=message.from_user.id)
    
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

📋 **Available Commands:**
   • `/help` - Show this guide 
   • `/stats` - Bot statistics 
   • `/about` - About this bot

❓ **Need Help? / Madad Chahiye?**
Just send the movie name and start searching!
Bas movie ka naam bhejein aur search shuru karein!
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel / Channel Join Karein", url=get_default_channel_link())]
    ])
    
    await message.reply(guide_text, reply_markup=keyboard)


# --- HELP COMMAND ---
@app.on_message(filters.command("help"))
async def help_command(client, message):
    help_text = """
📖 **Bot Help / Bot Madad**

**Available Commands :**

🔹 `/start` - Start the bot and see guide

🔹 `/help` - Show this help message

🔹 `/stats` - View bot statistics

🔹 `/about` - About this bot

🔹 `/movie <name>` (Groups only) - Search movie in groups

**How to Search / Kaise Search Karein:**
• In Private: Just type movie name
  Private mein: Bas movie ka naam type karein
• In Groups: Use /movie command
  Groups mein: /movie command use karein

**Example / Udaharan:**
Private: `Avengers Endgame`
Group: `/movie Avengers Endgame`
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=get_default_channel_link())]
    ])
    
    await message.reply(help_text, reply_markup=keyboard)


# --- STATS COMMAND ---
@app.on_message(filters.command("stats"))
async def stats_command(client, message):
    stats = get_stats()
    
    if not stats:
        await message.reply("❌ Unable to fetch statistics.")
        return
    
    total_movies = len(MOVIE_DB)
    total_size = get_total_database_size()
    
    stats_text = f"""
📊 **Bot Statistics / Bot Statistics**

**Database Info / Database Jaankari:**
🎬 Total Movies: **{total_movies:,}**
💾 Total Size: **{total_size}**
📺 Channels: **{len(CHANNELS)}**

**Usage Stats / Upyog Statistics:**
🔍 Total Searches: **{stats.get('total_searches', 0):,}**
   ├─ Private: **{stats.get('private_searches', 0):,}**
   └─ Groups: **{stats.get('group_searches', 0):,}**

📤 Files Sent: **{stats.get('files_sent', 0):,}**
❌ Failed Searches: **{stats.get('failed_searches', 0):,}**
👥 Unique Users: **{stats.get('unique_users', 0):,}**

📅 **Bot Started:** {stats.get('start_date', 'Unknown')}

**Performance / Karyadakshata:**
✅ Success Rate: **{((stats.get('total_searches', 0) - stats.get('failed_searches', 0)) / max(stats.get('total_searches', 1), 1) * 100):.1f}%**
📊 Avg. Files per User: **{(stats.get('files_sent', 0) / max(stats.get('unique_users', 1), 1)):.2f}**
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=get_default_channel_link())]
    ])
    
    await message.reply(stats_text, reply_markup=keyboard)


# --- ABOUT COMMAND ---
@app.on_message(filters.command("about"))
async def about_command(client, message):
    about_text = """
ℹ️ **About Movie Search Bot**
**Movie Search Bot Ke Baare Mein**

🎬 **What is this bot?**
This is an advanced movie search and download bot that helps you find and download movies quickly.
✨ **Features **
• Fast search with smart algorithm 
• Multiple channel support
• Pagination support for large results
• Size display for every file
• Auto-delete in groups (1 min)
• Bilingual support (English + Hindi)
💡 **Tips for Best Results:**
1. Use correct spelling
2. Try different variations
3. Check file size before downloading

📢 **Stay Updated:**
Join our channels for latest movies!
Nayi movies ke liye hamare channels join karein!
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=get_default_channel_link())],
        [InlineKeyboardButton("📊 View Stats", callback_data="view_stats")]
    ])
    
    await message.reply(about_text, reply_markup=keyboard)


# --- CALLBACK FOR STATS FROM ABOUT ---
@app.on_callback_query(filters.regex(r"^view_stats"))
async def view_stats_callback(client, callback: CallbackQuery):
    stats = get_stats()
    
    if not stats:
        await callback.answer("Unable to fetch stats", show_alert=True)
        return
    
    total_movies = len(MOVIE_DB)
    
    quick_stats = f"""
📊 Quick Stats:
🎬 Movies: {total_movies:,}
📺 Channels: {len(CHANNELS)}
🔍 Searches: {stats.get('total_searches', 0):,}
📤 Files Sent: {stats.get('files_sent', 0):,}
👥 Users: {stats.get('unique_users', 0):,}
"""
    
    await callback.answer(quick_stats, show_alert=True)


# --- PRIVATE SEARCH HANDLER ---
@app.on_message(filters.private & filters.text & ~filters.command(["start", "movie", "help", "stats", "about"]))
async def search_handler(client, message):
    # Check if message starts with "/" - treat as unknown command
    if is_command(message.text):
        await message.reply(
            "❌ Unknown command. Use /help to see available commands."
        )
        return
    
    user_query = message.text.strip().lower()
    words = user_query.split()
    if not words: 
        return

    update_stats("search", user_id=message.from_user.id, is_group=False)
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
        update_stats("failed_search")
        google_query = urllib.parse.quote(f"correct spelling of {message.text} movie")
        google_link = f"https://www.google.com/search?q={google_query}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Check Spelling on Google", url=google_link)]
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
    
    # Check rate limit
    can_proceed, wait_time = check_group_rate_limit(message.chat.id)
    if not can_proceed:
        await message.reply(f"⏳ Rate limit reached. Please wait {wait_time} seconds before next request.")
        return
    
    user_query = " ".join(message.command[1:]).strip().lower()
    words = user_query.split()
    
    update_stats("search", user_id=message.from_user.id, is_group=True)
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
        update_stats("failed_search")
        google_query = urllib.parse.quote(f"correct spelling of {user_query} movie")
        google_link = f"https://www.google.com/search?q={google_query}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Check Spelling on Google", url=google_link)]
        ])
        
        await status_msg.edit(f"❌ No results found. Please check spelling.", reply_markup=keyboard)
        return
    
    USER_SESSIONS[message.from_user.id] = found_movies
    await show_group_page(client, message.chat.id, message.from_user.id, page=1, status_msg=status_msg)
    
    # Schedule deletion of result message after 2 minutes
    asyncio.create_task(delete_after_delay(status_msg, 120))


# --- HELPER: DELETE MESSAGE AFTER DELAY ---
async def delete_after_delay(message, delay):
    """Delete a message after specified delay in seconds"""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except:
        pass


# --- PAGINATION CALLBACK (Private) ---
@app.on_callback_query(filters.regex(r"^page_"))
async def page_callback(client, callback: CallbackQuery):
    page = int(callback.data.split("_")[1])
    await show_page(client, callback.message.chat.id, callback.from_user.id, page=page, status_msg=callback.message)
    await callback.answer()


# --- PAGINATION CALLBACK (Group) ---
@app.on_callback_query(filters.regex(r"^grp_page_"))
async def group_page_callback(client, callback: CallbackQuery):
    page = int(callback.data.split("_")[2])
    await show_group_page(client, callback.message.chat.id, callback.from_user.id, page=page, status_msg=callback.message)
    await callback.answer()


@app.on_callback_query(filters.regex(r"^ignore"))
async def ignore_callback(client, callback: CallbackQuery):
    await callback.answer("Current Page info")


# --- DOWNLOAD CALLBACK (Private Only) ---
@app.on_callback_query(filters.regex(r"^dl_"))
async def send_movie_callback(client, callback: CallbackQuery):
    file_id = int(callback.data.split("_")[1])
    
    movie_info = next((m for m in MOVIE_DB if m['id'] == file_id), None)
    
    # Get the correct channel info for this movie
    channel_info = CHANNEL_MAP.get(file_id)
    if not channel_info:
        await callback.answer("Error: Channel information not found", show_alert=True)
        return
    
    await callback.answer("Sending file...")
    update_stats("download", user_id=callback.from_user.id)
    
    try:
        f_size = get_readable_size(movie_info['size']) if movie_info else ""
        f_name = movie_info['name'] if movie_info else "Movie File"
        
        custom_caption = (
            f"<a href='{channel_info['channel_link']}'>{f_name}</a>\n"
            f"<b>Size:</b> {f_size}\n\n"
            f"📱Phone MXPlayer 💻PC VLC for better experiance\n"
           
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢Join Channel for update and for backup this bot ban soon..", url=channel_info['channel_link'])]
        ])

        await client.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=channel_info['channel_id'],
            message_id=file_id,
            caption=custom_caption,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        await callback.message.reply(f"Error: {e}")


# --- DOWNLOAD CALLBACK (Group Only) ---
@app.on_callback_query(filters.regex(r"^grp_dl_"))
async def send_group_movie_callback(client, callback: CallbackQuery):
    # Check rate limit
    can_proceed, wait_time = check_group_rate_limit(callback.message.chat.id)
    if not can_proceed:
        await callback.answer(f"⏳ Rate limit reached. Wait {wait_time}s", show_alert=True)
        return
    
    file_id = int(callback.data.split("_")[2])
    
    movie_info = next((m for m in MOVIE_DB if m['id'] == file_id), None)
    
    # Get the correct channel info for this movie
    channel_info = CHANNEL_MAP.get(file_id)
    if not channel_info:
        await callback.answer("Error: Channel information not found", show_alert=True)
        return
    
    await callback.answer("Sending file...")
    update_stats("download", user_id=callback.from_user.id)
    update_group_rate_limit(callback.message.chat.id)
    
    try:
        # Get group link
        group_link = await get_group_link(client, callback.message.chat.id)
        
        f_size = get_readable_size(movie_info['size']) if movie_info else ""
        f_name = movie_info['name'] if movie_info else "Movie File"
        
        # Build caption with text links (no buttons)
        custom_caption = f"{f_name}\n<b>Size:</b> {f_size}\n\n"
        
        # Add group link as text if available
        if group_link:
            custom_caption += f"<a href='{group_link}'>Join Group</a>\n"
        
        # Add movie channel link as text
        custom_caption += f"<a href='{channel_info['channel_link']}'>Join Movie Channel</a>"

        sent_msg = await client.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=channel_info['channel_id'],
            message_id=file_id,
            caption=custom_caption,
            parse_mode=enums.ParseMode.HTML
        )
        
        # Tag the user and notify about deletion
        user_mention = f"<a href='tg://user?id={callback.from_user.id}'>{callback.from_user.first_name}</a>"
        notification_text = (
            f"Hey {user_mention}! ⚠️\n\n"
            f"Your file will be deleted in 1 minute to avoid copyright issues.\n"
            f"Please forward it somewhere safe now!\n\n"
            f"आपकी file 1 minute में delete हो जाएगी।\n"
            f"कृपया इसे कहीं safe forward कर लें!"
        )
        
        notification_msg = await client.send_message(
            chat_id=callback.message.chat.id,
            text=notification_text,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=sent_msg.id
        )
        
        # Delete file after 1 minute
        await asyncio.sleep(60)
        await sent_msg.delete()
        
        # Also delete notification message
        try:
            await notification_msg.delete()
        except:
            pass
        
    except Exception as e:
        await callback.message.reply(f"Error: {e}")


print("Bot Started...")
app.run()

