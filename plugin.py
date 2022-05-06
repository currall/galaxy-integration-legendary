import asyncio
import csv
import json
import logging
import os
import sys
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

from galaxy.api.consts import LicenseType, Platform
from galaxy.api.plugin import Plugin, create_and_run_plugin
from galaxy.api.types import Game, LicenseInfo, LicenseType, Authentication, LocalGame, NextStep, GameTime

now = datetime.now()
currentdir = os.path.dirname(__file__)
logger = logging.getLogger(__name__)

configfile = open(currentdir+"\\config.txt","r")
config = configfile.readlines()
legendary_location = config[0].replace("legendary: ","")

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
        
        self.checking_for_new_games = False

    async def launch_game(self, game_id):
        #os.system('"G:\Program Files (x86)\Legendary\legendary.exe" launch ' + game_id)
        os.system('"'+legendary_location+'\legendary.exe" launch ' + game_id)

    async def install_game(self, game_id):
        #os.system('start cmd.exe /c ""G:\Program Files (x86)\Legendary\legendary.exe" install '+game_id+'" -y')
        os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" install '+game_id+'" -y')

    async def uninstall_game(self, game_id):
        #os.system('start cmd.exe /c ""G:\Program Files (x86)\Legendary\legendary.exe" uninstall '+game_id+'" -y')
        os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" uninstall '+game_id+'" -y')

    async def get_owned_games(self) -> List[Game]:
        games = []
        p = subprocess.Popen('"'+legendary_location+'\legendary.exe" list-games', stdout=subprocess.PIPE, shell=True)

        output = str(p.communicate())
        print(output)

        printing = False
        game_name = ""

        for i in range(len(output)-3):
            
            if output[i] == "*":
                printing = True
            elif output[i+3] == "(":
                printing = False

            if printing:
                game_name += output[i+2]
            elif not printing and game_name != "":
                print(game_name)

                game_id = ""
                j = i+14

                while output[j] != " ":
                    game_id = game_id+output[j]
                    j+=1

                print(game_id)

                game = Game(
                    game_id=game_id,
                    game_title=game_name,
                    dlcs=[],
                    license_info=LicenseInfo(LicenseType.SinglePurchase)
                )
                        
                games.append(game)
                logger.info(game)
                game_name = ""

        return games

    async def get_local_games(self) -> List[Game]:
        games = []
        p = subprocess.Popen('"'+legendary_location+'\legendary.exe" list-installed', stdout=subprocess.PIPE, shell=True)

        output = str(p.communicate())
        print(output)

        printing = False
        game_name = ""

        for i in range(len(output)-3):
            
            if output[i] == "*":
                printing = True
            elif output[i+3] == "(":
                printing = False

            if printing:
                game_name += output[i+2]
            elif not printing and game_name != "":
                print(game_name)

                game_id = ""
                j = i+14

                while output[j] != " ":
                    game_id = game_id+output[j]
                    j+=1

                print(game_id)

                game = LocalGame(
                    game_id,
                    1
                )
                        
                games.append(game)
                logger.info(game)
                game_name = ""

        return games

    async def authenticate(self, stored_credentials=None):
        """
        Not needed, but needs to return a galaxy.api.types.Authentication for GOG to work.\n
        Also, to stay connected we need to persist credentials here (locally in the plugin's .db file).\n
        Overrides Plugin.authenticate
        """
        # Use stored_credentials (persisted locally in the plugin's .db-file) or create new creds and store them immediately
        new_credentials = dict(
            {"user_id": "legendary", "user_name": "legendary"})
        creds = stored_credentials or new_credentials
        self.store_credentials(creds)
        return Authentication(creds["user_id"], creds["user_name"])

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
