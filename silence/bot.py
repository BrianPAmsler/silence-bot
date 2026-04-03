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
from bot_states import *

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.guilds = True
intents.members = True
intents.voice_states = True

client = discord.Client(intents=intents)

user_state = {}

async def process_dm_command(message: discord.Message, state: UserState) -> UserState:
    # Maybe replace big if statement with a polymorphic class
    if state.name == "Default":
        return await default_state(client, message)
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
    else:
        user_state[message.author.id].timestamp = datetime.datetime.now()

@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # When a user leaves a channel, before.channel is Some and after.channel is None
    if before.channel is None:
        return
    
    members = [member for member in before.channel.members if member.id != client.user.id]

    if len(members) == 0:
        await asyncio.sleep(config.get_config().empty_server_timeout)
        # Get a new 
        channel = client.get_channel(before.channel.id)
        members = [member for member in channel.members if member.id != client.user.id]
        if len(members) == 0:
            await voice.disable_channel(before.channel)

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

def start():
    print("Loading configs...")
    config.get_config()
    config.load_server_configs()
    print("Logging in...")

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