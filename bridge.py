import re
import time
import asyncio
import requests
import discord
import os
from discord.ext import commands
from mcrcon import MCRcon, MCRconException
import configparser

# Configuration Import
config = configparser.ConfigParser()
try:
    config_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    config.read(config_file_path)
except Exception as e:
    print("Can't open config file (config.ini); {e}")
    exit
MC_LOG_FILE_PATH = config['minecraft']['log_file_path']
MINECRAFT_SERVER_IP = config['minecraft']['server_ip']
RCON_PORT = config.getint('minecraft', 'rcon_port')
RCON_PASSWORD = config['minecraft']['rcon_password']
DISCORD_BOT_TOKEN = config['discord']['bot_token']
DISCORD_CHANNEL_ID = config.getint('discord', 'channel_id')

# Regex for Minecraft server log filtering
#\1 is username, \2 is message
REGEX_MC_MESSAGE = r'\[\d\d:\d\d:\d\d\] \[Server thread\/INFO\]: <(\w*)> (.*)'
REGEX_MC_MEACTION = r'\[\d\d:\d\d:\d\d\] \[Server thread\/INFO\]: \* (\w*) (.*)'
REGEX_MC_ACTIVITY = r'\[\d\d:\d\d:\d\d\] \[Server thread\/INFO\]: (\w*) ((?!\(.*\))(?!lost connection:).*)'

# Define the intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
# Set up Discord bot
bot = commands.Bot(command_prefix="#!", intents=intents)

# RCON Manager
class RconManager:
    def __init__(self, ip, port, password):
        self.ip = ip
        self.port = port
        self.password = password
        self.connection = None

    def connect(self):
        try:
            self.connection = MCRcon(self.ip, self.password, port=self.port)
            self.connection.connect()
            print(f'Connected with Rcon.', flush=True)
        except MCRconException as e:
            print(f'Rcon conn failed: {e}', flush=True)
            self.connection = None

    def send_command(self, command):
        if self.connection is None:
            self.connect()
        try:
            self.connection.command(command)
        except MCRconException:
            print(f'Rcon cmd failed, attempting reconn...', flush=True)
            self.disconnect()
            time.sleep(3)
            self.connect()
            if self.connection:
                self.connection.command(command)

    def disconnect(self):
        if self.connection:
            self.connection.disconnect()
            self.connection = None
            print(f'Disconnected from Rcon.', flush=True)

# Initialize RCON Manager
rcon_manager = RconManager(MINECRAFT_SERVER_IP, RCON_PORT, RCON_PASSWORD)
rcon_manager.connect()

# Function to send message to Discord
def send_to_discord(message):
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    asyncio.run_coroutine_threadsafe(channel.send(message), bot.loop)

# Function to send command to Minecraft server via RCON
def send_to_minecraft(command):
	rcon_manager.send_command(command)

# Background task to check Minecraft server log file
async def check_minecraft_log():
    await bot.wait_until_ready()
    last_size = 0

    while not bot.is_closed():
        try:
            with open(MC_LOG_FILE_PATH, 'r') as log_file:
                log_file.seek(0, 2)  # Move to the end of the file
                while not bot.is_closed():
                    # Check if the log file has rotated
                    current_size = os.path.getsize(MC_LOG_FILE_PATH)
                    if current_size < last_size:
                        print(f'Log file rotated or truncated.', flush=True)
                        last_size = current_size
                        break
                    last_size = current_size
    
                    #log_file.seek(0, 2)  # Move to the end of the file
    
                    while not bot.is_closed():
                        line = log_file.readline()
                        if not line:
                            await asyncio.sleep(1)
                            break
                        message = line.strip()
                        
             			# Check each regex pattern
                        match_message = re.search(REGEX_MC_MESSAGE, message)
                        if match_message:
                            user, text = match_message.group(1), match_message.group(2)
                            send_to_discord(f"**{user}**: {text}")
    		
                        match_action = re.search(REGEX_MC_MEACTION, message)
                        if match_action:
                            user, text = match_action.group(1), match_action.group(2)
                            send_to_discord(f"\* ***{user}*** {text}")
    
                        match_activity = re.search(REGEX_MC_ACTIVITY, message)
                        if match_activity:
                            user, text = match_activity.group(1), match_activity.group(2)
                            send_to_discord(f"{user} {text}")
    
                        await asyncio.sleep(0.1)
        except FileNotFoundError:
            print(f'Log file not found, retrying in 3...', flush=True)
            await asyncio.sleep(3)

# Event listener for Discord messages
@bot.event
async def on_message(message):
    if message.channel.id == DISCORD_CHANNEL_ID and not message.author.bot:
        def replace_urls(text):
            url_regex = r'(https?://[^\s]+)'
            return re.sub(url_regex, lambda match: f"<{match.group(0).split('/')[2]} link>", text)
		
        def sanitize_emotes(text):
            emote_regex = r'<a?(:\w+:)\d+>'
            return re.sub(emote_regex, r'\1', text)

        def sanitize_mentions(text):
            return text.replace('@', '®')

        def split_long_message(text, limit=200):
            return [text[i:i+limit] for i in range(0, len(text), limit)]

        modified_content = replace_urls(message.content)
        modified_content = sanitize_emotes(modified_content)
        
        # Resolve user and channel mentions
        for user in message.mentions:
            modified_content = modified_content.replace(f"<@{user.id}>", f"@{user.nick}")
        for role in message.role_mentions:
            modified_content = modified_content.replace(f"<@&{role.id}>", f"@{role.name}")
        for channel in message.channel_mentions:
            modified_content = modified_content.replace(f"<#{channel.id}>", f"#{channel.name}")

        # Check for images and embeds
        if message.attachments:
            modified_content = "<image> " + modified_content
        if message.embeds:
            modified_content += " <embed>"

        # Prepend reply info if the message is a reply
        if message.reference and message.reference.resolved:
            replied_user = message.reference.resolved.author.display_name
            if isinstance(message.reference.resolved, discord.Message):
                guild = message.guild
                replied_member = guild.get_member(message.reference.resolved.author.id)
                if replied_member:
                    replied_user = replied_member.nick or replied_member.name
            modified_content = f"(§oreply @{replied_user}§r§b) {modified_content}"

        modified_content = sanitize_mentions(modified_content)
        
        # Split and send long messages
        message_segments = split_long_message(modified_content)
        for segment in message_segments:
            send_to_minecraft(f"say <{message.author.nick}> §b{segment}")
            if len(message_segments) > 1:
                time.sleep(0.2)

    await bot.process_commands(message)

# Start background task
@bot.event
async def on_ready():
    bot.loop.create_task(check_minecraft_log())
    print(f'Logged into Discord as {bot.user}!', flush=True)

# Run Discord bot
bot.run(DISCORD_BOT_TOKEN)

# Ensure Rcon closed at exit
import atexit
atexit.register(rcon_manager.disconnect)
