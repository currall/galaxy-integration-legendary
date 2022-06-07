import asyncio
import csv
import json
import logging
import os
import sys
import subprocess

from time import sleep
from datetime import datetime
from typing import Dict, List, Optional

from galaxy.api.consts import LicenseType, Platform
from galaxy.api.plugin import Plugin, create_and_run_plugin
from galaxy.api.types import Game, LicenseInfo, LicenseType, Authentication, LocalGame, NextStep, GameTime

now = datetime.now()
currentdir = os.path.dirname(__file__)
logger = logging.getLogger(__name__)

def read_config():

    try:
        configfile = open(currentdir+"\\config.txt","r")
        config = configfile.readlines()
    except:
        pass

    try:
        legendary_location = config[0].replace("legendary: ","")
        legendary_location = legendary_location.replace("\n","")

        if not os.path.isfile(legendary_location+'\legendary.exe'):
            legendary_location = currentdir+"\\legendary"
    except:
        legendary_location = currentdir+"\\legendary"

    try:
        launch_flags = config[1].replace("launch flags:","")
        launch_flags = launch_flags.replace("\n","")
    except:
        launch_flags = ""

    try:
        update_check = config[2]
    except:
        update_check = true
        
    return [configfile, config, legendary_location, launch_flags, update_check]
        
[configfile, config, legendary_location, launch_flags, update_check] = read_config()

class LegendaryPlugin(Plugin):
    def __init__(self, reader, writer, token):
        super().__init__(
            Platform.Epic,  # Platform.Something
            read_manifest(),  # "1.0"
            reader,
            writer,
            token
        )
        self.owned_game_cache = self.generate_gamelist(0,1)
        self.local_game_cache = self.generate_gamelist(1,1)
        self.owned_game_name_cache = self.generate_gamelist(0,2)
        
        self.ticks = 0        
        self.checking_for_new_games = False
    
    def tick(self):
    
        owned_gameslist = []
        owned_gamesnamelist = []
        local_gameslist = []
    
        logger.info("start tick")
        
        self.ticks += 1
        
        if self.ticks % 1 == 0:
            
            local_gameslist = self.generate_gamelist(1,1)
            logger.info("installed games list generated")
        
            for i in range(len(local_gameslist)):
                if local_gameslist[i] not in self.local_game_cache:
                    self.update_local_game_status(LocalGame(local_gameslist[i], 1))
                    logger.info("New installed game: ",local_gameslist[i])
        
        if self.ticks % 5 == 0:
        
            local_gameslist = self.generate_gamelist(1,1)
            logger.info("installed games list generated (uninstalled game function)")
        
            for i in range(len(self.local_game_cache)):
                if self.local_game_cache[i] not in local_gameslist:
                    self.update_local_game_status(LocalGame(self.local_game_cache[i], 0))
                    logger.info("New uninstalled game: ",local_gameslist[i])
        
        if self.ticks % 9 == 0:
        
            owned_gameslist = self.generate_gamelist(0,1)
            logger.info("owned game ids list generated")
            owned_gamesnamelist = self.generate_gamelist(0,2)
            logger.info("owned games list generated")
        
            for i in range(len(owned_gameslist)):
                if owned_gameslist[i] not in self.owned_game_cache:
                    new_game = Game(
                        game_id=owned_gameslist[i],
                        game_title=owned_gamesnamelist[i],
                        dlcs=[],
                        license_info=LicenseInfo(LicenseType.SinglePurchase)
                    )
                    self.add_game(new_game)
                    logger.info("New game: ",owned_gameslist[i])
        
        logger.info("tick complete")

    async def launch_game(self, game_id):
        #os.system('"G:\Program Files (x86)\Legendary\legendary.exe" launch ' + game_id)
        if "false" not in update_check.lower():
            os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" update '+game_id+'"')
        os.system('"'+legendary_location+'\legendary.exe" launch ' + game_id + launch_flags)
    
    async def install_game(self, game_id):
        #os.system('start cmd.exe /c ""G:\Program Files (x86)\Legendary\legendary.exe" install '+game_id+'" -y')
        os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" install '+game_id+'"')

    async def uninstall_game(self, game_id):
        #os.system('start cmd.exe /c ""G:\Program Files (x86)\Legendary\legendary.exe" uninstall '+game_id+'" -y')
        os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" uninstall '+game_id+'"')
    '''
    async def get_local_size(self, game_id, context):
        sizelist = self.generate_gamelist(1,3)
        logger.info(sizelist)
        
        for i in range(len(sizelist)):
            logger.info(game_id)
            if game_id == sizelist[i][0]:
                install_size = sizelist[i][1]
        
        install_size = int(float(install_size)*1000000000)
        logger.info(install_size)     
        return install_size
    '''
    def generate_gamelist(self, installed, type):
    
    # declaring lists
        owned_games = []
        local_games = []
        
        owned_game_ids = []
        local_game_ids = []
        
        owned_game_names = []
        local_game_names = []
        
        local_game_sizes = []
    # commands
        owned_games_command = subprocess.Popen('"'+legendary_location+'\legendary.exe" list-games', stdout=subprocess.PIPE, shell=True)
        local_games_command = subprocess.Popen('"'+legendary_location+'\legendary.exe" list-installed', stdout=subprocess.PIPE, shell=True)

        owned_games_output = str(owned_games_command.communicate())
        local_games_output = str(local_games_command.communicate())
# local games   
        for i in range(len(local_games_output)):
# local game names
            if local_games_output[i-2:i] == "* ":
                game_name = ""
                loop = i
                while local_games_output[loop+1:loop+3] != "(A":
                    game_name = game_name + local_games_output[loop]
                    loop += 1
                local_game_names.append(game_name)
# local game ids
            if local_games_output[i:i+11] == "(App name: ":
                game_id = ""
                loop = i + 11
                while local_games_output[loop] + local_games_output[loop+1] != " |":
                    game_id = game_id + local_games_output[loop]
                    loop += 1
                local_game_ids.append(game_id)
                local_game = LocalGame(
                    game_id,
                    1
                )
                local_games.append(local_game)
# local game size              
            if local_games_output[i:i+4] == " GiB":
                game_size = ""
                loop = i - 1
                while local_games_output[loop] != " ":
                    game_size = local_games_output[loop] + game_size
                    loop -= 1
                local_game_sizes.append([game_id,game_size])
# owned games       
        for i in range(len(owned_games_output)):
# owned game names
            if owned_games_output[i-2:i] == "* ":
                game_name = ""
                loop = i
                while owned_games_output[loop+1:loop+3] != "(A":
                    game_name = game_name + owned_games_output[loop]
                    loop += 1
                owned_game_names.append(game_name)
# owned game ids
            if owned_games_output[i:i+11] == "(App name: ":
                game_id = ""
                loop = i + 11
                while owned_games_output[loop] + owned_games_output[loop+1] != " |":
                    game_id = game_id + owned_games_output[loop]
                    loop += 1
                owned_game_ids.append(game_id)
                owned_game = Game(
                    game_id=game_id,
                    game_title=game_name,
                    dlcs=[],
                    license_info=LicenseInfo(LicenseType.SinglePurchase)
                )
                owned_games.append(owned_game)
        
        if installed == 0:
            if type == 0:
                return owned_games
            elif type == 1:
                return owned_game_ids
            elif type == 2:
                return owned_game_names
        
        elif installed == 1:
            if type == 0:
                return local_games
            elif type == 1:
                return local_game_ids
            elif type == 2:
                return local_game_names
            elif type == 3:
                return local_game_sizes

    async def get_owned_games(self) -> List[Game]:
        games = self.generate_gamelist(0,0)
        return games

    async def get_local_games(self) -> List[Game]:
        games = self.generate_gamelist(1,0)
        return games
        
    async def authenticate(self, stored_credentials=None):
        # Use stored_credentials (persisted locally in the plugin's .db-file) or create new creds and store them immediately
        new_credentials = dict(
            {"user_id": "legendary", "user_name": "legendary"})
        creds = stored_credentials or new_credentials
        self.store_credentials(creds)
        return Authentication("legendary", "legendary")

def main():
    """run plugin event loop. INTEGRATION"""
    create_and_run_plugin(LegendaryPlugin, sys.argv)


async def test():
    logging.basicConfig(filename='log.txt', level=logging.DEBUG)
    plugin = LegendaryPlugin(None, None, None)
    games = await plugin.get_owned_games()


def read_manifest():
    with open(os.path.join(currentdir, "manifest.json"), "r") as f:
        text = f.read()
        j = json.loads(text)
        version = j["version"]
        logger.info(version)
        return version


if __name__ == "__main__":
    main()
