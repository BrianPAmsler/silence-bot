import datetime
import voice
import discord
import config_local as config
import asyncio
import probability
import soundfile
import io
import numpy as np
import shlex

from typing import Any

SERVER_MSG = "Type `add-sound <voice-channel-id>` to add a sound to a voice channel.\n" \
            "Type `list-sounds <voice-channel-id>` to see all sounds currently in a channel.\n " \
            "Type `remove-sound <voice-channel-id> <sound-number>` to remove a sound from the channel.\n" \
            "Type `give-user-permission <user-id>` to give a user permission to manage the bot on this server.\n" \
            "Type `remove-user-permisssion <user-id>` to remove manage permissions from a user.\n" \
            "Type `give-role-permission <role-id>` to give a role permission to manage the bot on this server.\n" \
            "Type `remove-role-permission <role-id>` to remove manage permissions from a role.\n" \
            "Type `enable <voice-channel-id>` to enable sounds in a channel.\n" \
            "Type `disable <voice-channel-id>` to disable sounds in a channel.\n"

class UserState:
    def __init__(self, name: str, data: Any = None):
        self.name = name
        self.data = data
        self.timestamp = datetime.datetime.now()

async def queue_sound(channel: discord.abc.GuildChannel, sound: config.Sound):
    delay = max(sound.data.duration, sound.distribution.sample() * 60)
    await asyncio.sleep(delay)
    
    if voice.is_enabled(channel) and sound in config.get_server_config(channel.guild.id).sounds:
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

        return UserState("ManageServer", server)
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

        return UserState("ManageServer", server)
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

    max_len = config.get_config().max_audio_clip_length
    if duration > max_len:
        await message.channel.send(f"Audio file must be {max_len} seconds or less.")
        return None
    
    await message.channel.send("Please choose which type of random distribution you would like to use for randomly playing your sound.\n" \
        "Type either `linear` or `normal`.")
    return UserState("Distribution", (server, channel, sound_files[0].filename, voice.ReplayableAudioSource(discord.FFmpegPCMAudio(bytes, pipe=True), duration)))

async def manage_server(message: discord.Message, server: discord.Guild) -> UserState:
    command, *args = shlex.split(message.content)
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
    elif command == "list-sounds":
        channel_id = 0
        if len(args) == 1:
            channel_id = int(args[0])
        channel = server.get_channel(channel_id)

        if channel is None or channel.type != discord.ChannelType.voice:
            await message.channel.send("Invalid channel id.")
            return None
        
        cfg = config.get_server_config(server.id)
        if cfg is None:
            await message.channel.send("Invalid channel id.")
            return None
        sounds = [sound for sound in cfg.sounds if sound.channel_id == channel_id]

        if len(sounds) <= 0:
            await message.channel.send("No sounds in channel.")
            return None

        msg = ""
        for i, sound in enumerate(sounds):
            msg += f"{i + 1}) {sound.name} [{sound.distribution.to_str()}]\t"
        
        await message.channel.send(msg)
    elif command == "remove-sound":
        channel_id = 0
        if len(args) == 2:
            channel_id = int(args[0])
        channel = server.get_channel(channel_id)

        if channel is None or channel.type != discord.ChannelType.voice:
            await message.channel.send("Invalid channel id.")
            return None
    
        try:
            sound_number = int(args[1]) - 1
        except ValueError:
            await message.channel.send("Sound number must be an integer.")
            return None
        
        cfg = config.get_server_config(server.id)
        if cfg is None:
            await message.channel.send("Invalid channel id.")
            return None
        sounds = [sound for sound in cfg.sounds if sound.channel_id == channel_id]

        if sound_number < 0 or sound_number >= len(sounds):
            await message.channel.send("Invalid sound number.")
            return None
        
        sound = sounds[sound_number]
        cfg.sounds.remove(sound)
        config.update_server_config(server.id, cfg)

        await message.channel.send("Sound removed.")

        return None
    elif command == "enable":
        channel_id = 0
        if len(args) == 1:
            channel_id = int(args[0])
        channel = server.get_channel(channel_id)

        if channel is None or channel.type != discord.ChannelType.voice:
            await message.channel.send("Invalid channel id.")
            return None
        
        await voice.enable_channel(channel)
        event_loop = asyncio.get_event_loop()
        cfg = config.get_server_config(server.id)

        for sound in cfg.sounds:
            if sound.channel_id == channel_id:
                event_loop.create_task(queue_sound(channel, sound))

        await message.channel.send("Channel enabled.")

        return None
    elif command == "disable":
        channel_id = 0
        if len(args) == 1:
            channel_id = int(args[0])
        channel = server.get_channel(channel_id)

        if channel is None or channel.type != discord.ChannelType.voice:
            await message.channel.send("Invalid channel id.")
            return None
        
        await voice.disable_channel(channel)

        await message.channel.send("Channel disabled.")

        return None
    elif command == "give-user-permission":
        user_id = 0
        if len(args) == 1:
            user_id = int(args[0])
        member = server.get_member(user_id)

        if member is None:
            await message.channel.send("User id invalid or user is not a member of the server.")
            return None
        
        cfg = config.get_server_config(server.id)
        
        if user_id in cfg.elevated_members:
            await message.channel.send("User already has permission.")
            return None
        
        cfg.elevated_members.append(user_id)
        config.update_server_config(server.id, cfg)

        await message.channel.send("Permission granted.")
        return None
    elif command == "remove-user-permission":
        user_id = 0
        if len(args) == 1:
            user_id = int(args[0])
        member = server.get_member(user_id)

        if member is None:
            await message.channel.send("User id invalid or user is not a member of the server.")
            return None
        
        cfg = config.get_server_config(server.id)
        
        cfg.elevated_members.remove(user_id)
        config.update_server_config(server.id, cfg)

        await message.channel.send("Permission removed.")
        return None
    elif command == "give-role-permission":
        role = None
        if len(args) == 1:
            role = discord.utils.get(server.roles, name=args[0])

        if role is None:
            await message.channel.send("Cannot find role.")
            return None
        
        cfg = config.get_server_config(server.id)
        
        if role.id in cfg.elevated_roles:
            await message.channel.send("Role already has permission.")
            return None
        
        cfg.elevated_roles.append(role.id)
        config.update_server_config(server.id, cfg)

        await message.channel.send("Permission granted.")
        return None
    elif command == "remove-role-permission":
        role = None
        if len(args) == 1:
            role = discord.utils.get(server.roles, name=args[0])

        if role is None:
            await message.channel.send("Cannot find role.")
            return None
        
        cfg = config.get_server_config(server.id)
        
        cfg.elevated_roles.remove(role.id)
        config.update_server_config(server.id, cfg)

        await message.channel.send("Permission removed.")
        return None
    elif command == "has-permission":
        user_id = 0
        if len(args) == 1:
            user_id = int(args[0])
        member = server.get_member(user_id)

        if member is None:
            await message.channel.send("User id invalid or user is not a member of the server.")
            return None
        
        await message.channel.send(str(has_permission(member)))
        return None
    elif command == "help":
        await message.channel.send(SERVER_MSG)
        return None
    
    return None

def has_permission(member: discord.Member) -> bool:
    cfg = config.get_server_config(member.guild.id)
    return member.guild_permissions.administrator \
        or member.id in cfg.elevated_members \
        or len((set(cfg.elevated_roles) & set([role.id for role in member.roles]))) > 0

async def default_state(client: discord.Client, message: discord.Message) -> UserState:
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
            return None

        member = server.get_member(message.author.id)

        if member is None:
            await message.channel.send("You are not a member of this server.")
            return None
        
        if not has_permission(member):
            await message.channel.send("You do not have permission to manage this server.")
            return None

        await message.channel.send(SERVER_MSG)
        
        return UserState("ManageServer", server)
    
    await message.channel.send("Type `help` for more info.")

    return None
