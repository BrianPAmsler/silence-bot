# This example requires the 'message_content' intent.

from typing import Any

import discord
import logging
import datetime
import config_local as config
import probability
import jsonpickle
import soundfile
import io
import asyncio
import voice
import numpy as np

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.guilds = True
intents.members = True
intents.voice_states = True

client = discord.Client(intents=intents)

class UserState:
    def __init__(self, name: str, data: Any = None):
        self.name = name
        self.data = data
        self.timestamp = datetime.datetime.now()

user_state: dict[int, UserState] = {}

async def queue_sound(channel: discord.abc.GuildChannel, sound: config.Sound):
    delay = max(sound.data.duration, sound.distribution.sample() * 60)
    print(delay)
    await asyncio.sleep(delay)
    
    if sound in config.get_server_config(channel.guild.id).sounds:
        print("play sound: " + sound.name) # actually play sound
        await voice.play_sound(channel, sound.data)
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(queue_sound(channel, sound))

async def choose_distribution(message: discord.Message, server: discord.Guild, channel: discord.abc.GuildChannel, name: str, data: voice.ReplayableAudioSource) -> UserState:
    if message.content == "linear":
        await message.channel.send("Please type the minimum delay in minutes:")
        return UserState("LinearMin", (server, channel, name, data))
    elif message.content == "normal":
        await message.channel.send("Please type the mean delay in minutes:")
        return UserState("NormalMean", (server, channel, name, data))
    else:
        await message.channel.send("Please choose either `linear` or `normal`.")

    return None

async def linear_min(message: discord.Message, server: discord.Guild, channel: discord.abc.GuildChannel, name: str, data: voice.ReplayableAudioSource) -> UserState:
    try:
        value = float(message.content)
        if value < 0:
            await message.channel.send("Value must be greater than zero.")
            return None
        
        await message.channel.send("Please type the maximum delay in minutes:")

        return UserState("LinearMax", (server, channel, name, data, value))
    except ValueError:
        await message.channel.send("Input must be a number.")
        return None
    
async def linear_max(message: discord.Message, server: discord.Guild, channel: discord.abc.GuildChannel, name: str, data: voice.ReplayableAudioSource, min: float) -> UserState:
    try:
        value = float(message.content)
        if value < min:
            await message.channel.send(f"Value must be greater than the minimum ({min}).")
            return None
        
        sound = config.Sound(name, channel.id, data, probability.Linear(min, value))
        cfg = config.get_server_config(server.id)

        cfg.sounds.append(sound)
        config.update_server_config(server.id, cfg)

        event_loop = asyncio.get_event_loop()
        event_loop.create_task(queue_sound(channel, sound))
        
        await message.channel.send("Sound added.")

        return UserState("Default")
    except ValueError:
        await message.channel.send("Input must be a number.")
        return None
    
async def normal_mean(message: discord.Message, server: discord.Guild, channel: discord.abc.GuildChannel, name: str, data: voice.ReplayableAudioSource) -> UserState:
    try:
        value = float(message.content)
        if value < 0:
            await message.channel.send("Value must be greater than zero.")
            return None
        
        await message.channel.send("Please type the standard deviation:")

        return UserState("NormalSigma", (server, channel, name, data, value))
    except ValueError:
        await message.channel.send("Input must be a number.")
        return None
    
async def normal_sigma(message: discord.Message, server: discord.Guild, channel: discord.abc.GuildChannel, name: str, data: voice.ReplayableAudioSource, mean: float) -> UserState:
    try:
        value = float(message.content)
        if value < 0:
            await message.channel.send("Value must be greater than zero.")
            return None
        
        sound = config.Sound(name, channel.id, data, probability.Normal(mean, value))
        cfg = config.get_server_config(server.id)

        cfg.sounds.append(sound)
        config.update_server_config(server.id, cfg)
        
        event_loop = asyncio.get_event_loop()
        event_loop.create_task(queue_sound(channel, sound))

        await message.channel.send("Sound added.")

        return UserState("Default")
    except ValueError:
        await message.channel.send("Input must be a number.")
        return None

async def upload_sound(message: discord.Message, server: discord.Guild, channel: discord.abc.GuildChannel) -> UserState:
    sound_files: list[discord.Attachment] = []

    for attachment in message.attachments:
        if attachment.content_type.startswith("audio"):
            sound_files.append(attachment)

    if len(sound_files) == 0:
        await message.channel.send("Message does not contain a sound file.")
        return None
    
    bytes = io.BytesIO(await sound_files[0].read())
    data, samplerate = soundfile.read(bytes, dtype=np.int16)
    bytes.seek(0)
    duration = len(data) / float(samplerate)

    if duration > 10:
        await message.channel.send("Audio file must be 10 seconds or less.")
        return None
    
    await message.channel.send("Please choose which type of random distribution you would like to use for randomly playing your sound.\n" \
        "Type either `linear` or `normal`.")
    return UserState("Distribution", (server, channel, sound_files[0].filename, voice.ReplayableAudioSource(bytes, duration)))

async def manage_server(message: discord.Message, server: discord.Guild) -> UserState:
    command, *args = message.content.split(' ')
    if command == "add-sound":
        channel_id = 0
        if len(args) == 1:
            channel_id = int(args[0])
        channel = server.get_channel(channel_id)

        if channel is None or channel.type != discord.ChannelType.voice:
            await message.channel.send("Invalid channel id.")
            return None
        
        await message.channel.send("Please upload a sound file.")
        return UserState("UploadSound", (server, channel))
    
    return None

async def default_state(message: discord.Message) -> UserState:
    command, *args = message.content.split(' ')
    if command == "help":
        await message.channel.send(
            "Type `server <server_id>` to configure a server.\n" \
            "Type `cancel` to cancel current action.")
        return None
    elif command == "server":
        id = 0
        if len(args) == 1:
            id = int(args[0])
        server = client.get_guild(id)

        if server is None:
            await message.channel.send("Invalid server id.")
            return UserState("Default")

        member = server.get_member(message.author.id)

        if member is None:
            await message.channel.send("You are not a member of this server.")
            return UserState("Default")
        
        if not member.guild_permissions.administrator:
            await message.channel.send("You do not have permission to manage this server.")
            return UserState("Default")

        await message.channel.send(
            "Type `add-sound <voice-channel-id>` to add a sound to a voice channel.\n" \
            "Type `give-user-permission <user-id>` to give a user permission to manage the bot on this server.\n" \
            "Type `remove-user-permisssion <user-id>` to remove manage permissions from a user.\n" \
            "Type `give-role-permission <role-id>` to give a role permission to manage the bot on this server.\n" \
            "Type `remove-role-permission <role-id>` to remove manage permissions from a role.")
        
        return UserState("ManageServer", server)
    
    await message.channel.send("Type `help` for more info.")

    return None


async def process_dm_command(message: discord.Message, state: UserState) -> UserState:
    if state.name == "Default":
        return await default_state(message)
    elif message.content.startswith('cancel'):
        await message.channel.send("Cancelled.")
        return UserState("Default")
    elif state.name == "ManageServer":
        return await manage_server(message, state.data)
    elif state.name == "UploadSound":
        server, channel = state.data
        return await upload_sound(message, server, channel)
    elif state.name == "Distribution":
        server, channel, name, data = state.data
        return await choose_distribution(message, server, channel, name, data)
    elif state.name == "LinearMin":
        server, channel, name, data = state.data
        return await linear_min(message, server, channel, name, data)
    elif state.name == "LinearMax":
        server, channel, name, data, min = state.data
        return await linear_max(message, server, channel, name, data, min)
    elif state.name == "NormalMean":
        server, channel, name, data = state.data
        return await normal_mean(message, server, channel, name, data)
    elif state.name == "NormalSigma":
        server, channel, name, data, mean = state.data
        return await normal_sigma(message, server, channel, name, data, mean)
    else:
        return None

@client.event
async def on_ready():
    update_servers()
    await play_sounds()
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message: discord.message.Message):
    if message.author == client.user:
        return
    
    if not isinstance(message.channel, discord.channel.DMChannel):
        return
    
    if message.author.id not in user_state or (datetime.datetime.now() - user_state[message.author.id].timestamp).seconds >= config.get_config().command_timeout:
        user_state[message.author.id] = UserState("Default")

    state =  await process_dm_command(message, user_state[message.author.id])

    if state is not None:
        user_state[message.author.id] = state

@client.event
async def on_guild_join(guild: discord.Guild):
    config.update_server_config(guild.id, config.ServerConfig())

@client.event
async def on_guild_remove(guild: discord.Guild):
    config.update_server_config(guild.id, None)

def update_servers():
    # Remove servers that are no longer connected
    for server in config.get_servers():
        exists = False
        for guild in client.guilds:
            if server == guild.id:
                exists = True
                break
        
        if not exists:
            config.update_server_config(server, None)

    # Add default config for connected servers that have no config
    for server in client.guilds:
        if config.get_server_config(server.id) is None:
            config.update_server_config(server.id, config.ServerConfig())

async def play_sounds():
    for server in config.get_servers():
        cfg = config.get_server_config(server)
        guild = client.get_guild(server)
        for sound in cfg.sounds:
            channel = guild.get_channel(sound.channel_id)
            await voice.enable_channel(channel)
            event_loop = asyncio.get_event_loop()
            event_loop.create_task(queue_sound(channel, sound))
            

def start():
    config.get_config()
    config.load_server_configs()

    try:
        with open("bot_token.txt") as file:
            token = file.read()

        client.run(token, log_level=logging.WARN)
    except FileNotFoundError:
        print("Please create the bot_token.txt file in the root directory of this proeject.")
    except discord.errors.LoginFailure:
        print("bot_token.txt does not contain a valid bot token.")
    except Exception as e:
        print("Error: " + str(e))