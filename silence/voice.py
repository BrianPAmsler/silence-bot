import discord
import asyncio
import config_local as config
import numpy as np
import io

__connections: dict[int, discord.VoiceClient] = {}

class ReplayableAudioSource(discord.AudioSource):
    def __init__(self, source: discord.AudioSource, duration: float):
        buffer = io.BytesIO()
        self.duration = duration
        
        chunk = source.read()
        self.chunk_size = len(chunk)
        while len(chunk) > 0:
            buffer.write(chunk)
            chunk = source.read()

        self.data = buffer
        self.data.seek(0)
        self.source_is_opus = source.is_opus()

    def read(self):
        return self.data.read(self.chunk_size)

    def is_opus(self):
        self.source_is_opus
    
    def seek(self, pos: int):
        self.data.seek(0)

async def enable_channel(channel: discord.VoiceChannel):
    global __connections

    if channel.id in __connections:
        return
    
    __connections[channel.id] = await channel.connect()

async def disable_channel(channel: discord.VoiceChannel):
    global __connections

    if channel.id in __connections:
        con = __connections[channel.id]
        await con.disconnect()
        del __connections[channel.id]

async def play_sound(channel: discord.VoiceChannel, sound: ReplayableAudioSource):
    global __connections

    if channel.id in __connections:
       con = __connections[channel.id]
       sound.seek(0)
       con.play(sound)