import asyncio
import csv
import json
import logging
import os
import sys
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

from http_client import AuthenticatedHttpClient, Credentials
from backend import EpicClient, LibraryItem, LibraryPlatform, Friend
from galaxy.api.consts import LicenseType, Platform
from galaxy.api.plugin import Plugin, create_and_run_plugin
from galaxy.api.types import Game, LicenseInfo, LicenseType, Authentication, LocalGame, NextStep, GameTime

now = datetime.now()
currentdir = os.path.dirname(__file__)
logger = logging.getLogger(__name__)

configfile = open(currentdir+"\\config.txt","r")
config = configfile.readlines()
legendary_location = config[0].replace("legendary: ","")
legendary_location = legendary_location.replace("\n","")

if not os.path.isfile(legendary_location+'\legendary.exe'):
    legendary_location = currentdir+"\\legendary"

launch_flags = config[1].replace("launch flags:","")
launch_flags = launch_flags.replace("\n","")

update_check = config[2]

class LegendaryPlugin(Plugin):
    def __init__(self, reader, writer, token):
        manifest = read_manifest()
        super().__init__(
            # Not working: generic, unknown
            manifest["platform"],  # Platform.Something
            manifest["version"],  # "1.0"
            reader,
            writer,
            token
        )
        self._http_client = AuthenticatedHttpClient(self.refresh_credentials, self.lost_authentication_dummy)
        self.owned_game_cache = self.generate_gamelist(2)
        self.local_game_cache = self.generate_gamelist(3)
        
        self.checking_for_new_games = False
    
    def tick(self):
        logger.info("tick")
        local_gameslist = self.generate_gamelist(3)
        
        for i in range(len(local_gameslist)):
            self.update_local_game_status(LocalGame(local_gameslist[i], 1))
            
        for i in range(len(self.local_game_cache)):
            if self.local_game_cache[i] not in local_gameslist:
                self.update_local_game_status(LocalGame(self.local_game_cache[i], 0))

    async def launch_game(self, game_id):
        #os.system('"G:\Program Files (x86)\Legendary\legendary.exe" launch ' + game_id)
        if "false" in update_check.lower():
            os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" update '+game_id+'"')
        os.system('"'+legendary_location+'\legendary.exe" launch ' + game_id + launch_flags)
    
    async def install_game(self, game_id):
        #os.system('start cmd.exe /c ""G:\Program Files (x86)\Legendary\legendary.exe" install '+game_id+'" -y')
        os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" install '+game_id+'"')

    async def uninstall_game(self, game_id):
        #os.system('start cmd.exe /c ""G:\Program Files (x86)\Legendary\legendary.exe" uninstall '+game_id+'" -y')
        os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" uninstall '+game_id+'"')

    def generate_gamelist(self, type):
    
        owned_games = []
        local_games = []
        
        owned_game_ids = []
        local_game_ids = []
        
        owned_games_command = subprocess.Popen('"'+legendary_location+'\legendary.exe" list-games', stdout=subprocess.PIPE, shell=True)
        local_games_command = subprocess.Popen('"'+legendary_location+'\legendary.exe" list-installed', stdout=subprocess.PIPE, shell=True)

        owned_games_output = str(owned_games_command.communicate())
        local_games_output = str(local_games_command.communicate())

        printing = False
        game_name = ""

        for i in range(len(owned_games_output)-4):
            
            if owned_games_output[i] == "*":
                printing = True
            elif owned_games_output[i+3] == "(" and owned_games_output[i+4] != ")":
                printing = False

            if printing:
                game_name += owned_games_output[i+2]
            elif not printing and game_name != "":

                game_id = ""
                j = i+14

                while owned_games_output[j] != " ":
                    game_id = game_id+owned_games_output[j]
                    j+=1
                
                owned_game = Game(
                    game_id=game_id,
                    game_title=game_name,
                    dlcs=[],
                    license_info=LicenseInfo(LicenseType.SinglePurchase)
                )
                
                owned_games.append(owned_game)
                owned_game_ids.append(game_id)
                
                game_name = ""
        
        printing = False       
        game_name = ""
                
        for i in range(len(local_games_output)-4):
            
            if local_games_output[i] == "*":
                printing = True
            elif local_games_output[i+3] == "(" and local_games_output[i+4] != ")":
                printing = False

            if printing:
                game_name += local_games_output[i+2]
            elif not printing and game_name != "":

                game_id = ""
                j = i+14

                while local_games_output[j] != " ":
                    game_id = game_id+local_games_output[j]
                    j+=1

                local_game = LocalGame(
                    game_id,
                    1
                )
                
                local_games.append(local_game)
                local_game_ids.append(game_id)
                
                game_name = ""
        
        logger.info(local_game_ids)

        if type == 0:
            return owned_games
        elif type == 1:
            return local_games
        elif type == 2:
            return owned_game_ids
        elif type == 3:
            return local_game_ids

    async def get_owned_games(self) -> List[Game]:
        games = self.generate_gamelist(0)
        return games

    async def get_local_games(self) -> List[Game]:
        games = self.generate_gamelist(1)
        return games
        
    def lost_authentication_dummy(self) -> None:
        """Until GVAL-1773 is solved"""
        logger.warning(
            'Authentication lost has been triggered but will not be send.'
            'The connected account may need reauthentication'
        )

    def _process_credentials(self, credentials) -> Credentials:
        assert credentials is not None, 'No stored credentials received'
        self._last_credentials_data = credentials
        return json.loads(credentials['auth_data'])

    async def refresh_credentials(self) -> Credentials:
        return self._process_credentials(
            await super().refresh_credentials(self._last_credentials_data, sensitive_params=True))

    async def authenticate(self, stored_credentials):
        credentials = self._process_credentials(stored_credentials)
        self._http_client.set_credentials(credentials)
        return Authentication(self._http_client.account_id, self._http_client.display_name)

def main():
    """run plugin event loop. INTEGRATION"""
    create_and_run_plugin(LegendaryPlugin, sys.argv)


async def test():
    logging.basicConfig(filename='log.txt', level=logging.DEBUG)
    plugin = LegendaryPlugin(None, None, None)
    dirtydebug("test.txt", "{} {}".format(plugin._platform, plugin._version))
    games = await plugin.get_owned_games()
    dirtydebug("test.txt", games)


def dirtydebug(path: str, text: str):
    """Dirty Debug Helper to log text to a file"""
    now = datetime.now()
    nowtext = now.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, 'a') as f:
        f.write("[" + nowtext + "] : ")
        f.write(str(text))
        f.write("\n")


def read_manifest() -> Dict[str, any]:
    """Reads the manifest.json and returns the "platform" (galaxy.api.types.Platform) and "version" (str) to use."""
    platformsmap = dict([
        ("gog", "Gog"),
        ("steam", "Steam"),
        ("psn", "Psn"),
        ("xboxone", "XBoxOne"),
        ("generic", "Generic"),
        ("origin", "Origin"),
        ("uplay", "Uplay"),
        ("battlenet", "Battlenet"),
        ("epic", "Epic"),
        ("bethesda", "Bethesda"),
        ("paradox", "ParadoxPlaza"),
        ("humble", "HumbleBundle"),
        ("kartridge", "Kartridge"),
        ("itch", "ItchIo"),
        ("nswitch", "NintendoSwitch"),
        ("nwiiu", "NintendoWiiU"),
        ("nwii", "NintendoWii"),
        ("ncube", "NintendoGameCube"),
        ("riot", "RiotGames"),
        ("wargaming", "Wargaming"),
        ("ngameboy", "NintendoGameBoy"),
        ("atari", "Atari"),
        ("amiga", "Amiga"),
        ("snes", "SuperNintendoEntertainmentSystem"),
        ("beamdog", "Beamdog"),#aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        ("d2d", "Direct2Drive"),
        ("discord", "Discord"),
        ("dotemu", "DotEmu"),
        ("gamehouse", "GameHouse"),
        ("gmg", "GreenManGaming"),
        ("weplay", "WePlay"),
        ("zx", "ZxSpectrum"),
        ("vision", "ColecoVision"),
        ("nes", "NintendoEntertainmentSystem"),
        ("sms", "SegaMasterSystem"),
        ("c64", "Commodore64"),
        ("pce", "PcEngine"),
        ("segag", "SegaGenesis"),
        ("neo", "NeoGeo"),
        ("sega32", "Sega32X"),
        ("segacd", "SegaCd"),
        ("3do", "_3Do"),
        ("saturn", "SegaSaturn"),
        ("psx", "PlayStation"),
        ("ps2", "PlayStation2"),
        ("n64", "Nintendo64"),
        ("jaguar", "AtariJaguar"),
        ("dc", "SegaDreamcast"),
        ("xboxog", "Xbox"),
        ("amazon", "Amazon"),
        ("gg", "GamersGate"),
        ("egg", "Newegg"),
        ("bb", "BestBuy"),
        ("gameuk", "GameUk"),
        ("fanatical", "Fanatical"),
        ("playasia", "PlayAsia"),
        ("stadia", "Stadia"),
        ("arc", "Arc"),
        ("eso", "ElderScrollsOnline"),
        ("glyph", "Glyph"),
        ("aionl", "AionLegionsOfWar"),
        ("aion", "Aion"),
        ("blade", "BladeAndSoul"),
        ("gw", "GuildWars"),
        ("gw2", "GuildWars2"),
        ("lin2", "Lineage2"),
        ("ffxi", "FinalFantasy11"),
        ("ffxiv", "FinalFantasy14"),
        ("totalwar", "TotalWar"),
        ("winstore", "WindowsStore"),
        ("elites", "EliteDangerous"),
        ("star", "StarCitizen"),
        ("psp", "PlayStationPortable"),
        ("psvita", "PlayStationVita"),
        ("nds", "NintendoDs"),
        ("3ds", "Nintendo3Ds"),
        ("pathofexile", "PathOfExile"),
        ("twitch", "Twitch"),
        ("minecraft", "Minecraft"),
        ("gamesessions", "GameSessions"),
        ("nuuvem", "Nuuvem"),
        ("fxstore", "FXStore"),
        ("indiegala", "IndieGala"),
        ("playfire", "Playfire"),
        ("oculus", "Oculus"),
        ("test", "Test"),
        ("rockstar", "Rockstar")])

    with open(os.path.join(currentdir, "manifest.json"), "r") as f:
        text = f.read()
        j = json.loads(text)
        platformid = j["platform"]
        version = j["version"]
        platform = platformsmap[platformid]
        return dict([("platform", Platform[platform]), ("version", version)])


if __name__ == "__main__":
    main()
    # asyncio.run(test())
