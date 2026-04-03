import json
import probability
import os
import jsonpickle
import copy
from os import path
from typing import Any
import discord

from voice import ReplayableAudioSource

class Config:
    def __init__(self, command_timeout: int = 300, empty_server_timeout: int = 120, max_audio_clip_length: float = 10):
        self.command_timeout = command_timeout
        self.empty_server_timeout = 120
        self.max_audio_clip_length = 10

class Sound:
    def __init__(self, name: str, channel_id: int, data: ReplayableAudioSource, distribution: probability.Distribution):
        self.name = name
        self.channel_id = channel_id
        self.data = data
        self.distribution = distribution

class ServerConfig:
    def __init__(self, elevated_roles: list = [], elevated_members: list = [], sounds: list = []):
        self.elevated_roles = elevated_roles
        self.elevated_members = elevated_members
        self.sounds = sounds

    def copy(self):
        return ServerConfig(self.elevated_roles.copy(), self.elevated_members.copy(), self.sounds.copy())

__global_config: Config = None
__server_config: dict = None

def get_config() -> Config:
    global __global_config
    if __global_config is None:
        with open("config/global.json", mode="r+") as file:
            data = file.read()
            loaded_config = {}
            try:
                loaded_config = json.loads(data)
            except:
                pass
            config = {}
            default_config = Config().__dict__
            for key in default_config.keys():
                if key in loaded_config:
                    value = default_config[key]
                    # Try to create an instance based on the default value from the given type
                    # otherwise use default value
                    try:
                        value = type(default_config[key]).__call__(loaded_config[key])
                    except:
                        pass

                    config[key] = value
                else:
                    config[key] = default_config[key]
            
            __global_config = Config(**config)
            file.seek(0)
            file.truncate()
            file.write(json.dumps(config, indent=4))
    
    return __global_config

def update_config(key: str, value: Any):
    global __global_config
    data = __global_config.__dict__

    if key not in data:
        raise KeyError('Config does not contain key: "' + key + '"')
    
    try:
        value = type(data[key]).__call__(value)
    except:
        raise ValueError("Cannot create type " + str(type(data[key])) + " from type " + str(type(value)) + ' for key "' + key + '"')
    
    with open("config/global.json", 'w') as file:
        file.write(json.dumps(data, indent=4))

def get_server_config(server_id: int) -> ServerConfig:
    global __server_config

    if __server_config is None:
        load_server_configs()

    if server_id not in __server_config:
        return None

    return __server_config[server_id].copy()

def load_server_configs():
    global __server_config

    __server_config = {}
    for config_file in os.listdir(path.join('config', 'servers')):
        name, ext = config_file.split('.', maxsplit=1)
        if ext != 'json':
            continue

        try:
            id = int(name)
        except:
            continue

        config_file = path.join('config', 'servers', config_file)
        
        try:
            with open(config_file, 'r') as file:
                json = file.read()
                data = jsonpickle.loads(json)
                config = ServerConfig(**data)
                __server_config[id] = config
        except:
            pass

def update_server_config(server_id: int, config: ServerConfig):
    global __server_config
    
    if __server_config is None:
        load_server_configs()

    filename = path.join('config', 'servers', str(server_id) + '.json')

    if config is None:
        if server_id in __server_config:
            del __server_config[server_id]
            try:
                os.remove(filename)
            except:
                pass
        return

    __server_config[server_id] = config.copy()
    try:
        with open(filename, 'w') as file:
            file.write(jsonpickle.dumps(config.__dict__, indent=4))
    except:
        pass

def get_servers() -> list:
    global __server_config
    
    if __server_config is None:
        load_server_configs()

    if __server_config is None:
        return []
    
    return list(__server_config.keys())