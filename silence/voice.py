import discord
import asyncio
import config_local as config
import numpy as np
import io

__connections: dict[int, discord.VoiceClient] = {}

class ReplayableAudioSource(discord.AudioSource):
    def __init__(self, data: io.BytesIO, duration: float):
        self.duration = duration
        self.data = data
        self.data.seek(0)
        self.source = discord.FFmpegPCMAudio(self.data, pipe=True)

    def __getstate__(self):
        state = self.__dict__.copy()

        del state['source']

        return state

    def read(self):
        return self.source.read()

    def is_opus(self):
        self.source.is_opus()
    
    def reset(self):
        self.data.seek(0)
        self.source = discord.FFmpegPCMAudio(self.data, pipe=True)

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
       sound.reset()
       con.play(sound)