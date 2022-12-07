import sys
import os
import subprocess
import json
import logging
import asyncio
import webbrowser
import typing as t

from galaxy.api.plugin import Plugin, create_and_run_plugin
from galaxy.api.consts import Platform, OSCompatibility
from galaxy.api.errors import FailedParsingManifest
from galaxy.api.types import (
    Authentication, Game, LicenseInfo, LicenseType,
    GameTime, LocalGame, LocalGameState, UserInfo
)

from version import __version__
from http_client import AuthenticatedHttpClient, Credentials
from backend import EpicClient, LibraryItem, LibraryPlatform, Friend
from local import LocalGamesProvider, ClientNotInstalled, GameManifest, \
    WIN, MAC, parse_manifests, get_third_party_game_location, local_client

AppName = str
Title = str

logger = logging.getLogger(__name__)

currentdir = os.path.dirname(__file__)
        
try:
    configfile = open(currentdir+"\\config.txt","r")
    config = configfile.readlines()
    
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
        
except:
    legendary_location = currentdir+"\\legendary"
    launch_flags = ""
    update_check = true

class EpicPlugin(Plugin):
    def __init__(self, reader, writer, token):
        super().__init__(Platform.Epic, __version__, reader, writer, token)
        self._http_client = AuthenticatedHttpClient(self.refresh_credentials, self.lost_authentication_dummy)
        self._epic_client = EpicClient(self._http_client)
        self._local_client = local_client
        self._local_provider = LocalGamesProvider(
            self._local_client.launcher_process_identifier,
            get_third_party_game_location
        )
        
        #self._owned_game_cache = self.generate_gamelist(0,1)
        self._local_game_cache = self.generate_gamelist(1,1)
        #self._owned_game_name_cache = self.generate_gamelist(0,2)
        
        self._last_credentials_data = None
        self._refresh_owned_task: t.Optional[asyncio.Task] = None
        
    def generate_gamelist(self, installed, type):
    
        if installed == 0:
        
            owned_games = []
            owned_game_ids = []
            owned_game_names = []
            
            owned_games_command = subprocess.Popen('"'+legendary_location+'\legendary.exe" list-games', stdout=subprocess.PIPE, shell=True)
            owned_games_output = str(owned_games_command.communicate())
        
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
        
            if type == 0:
                return owned_games
            elif type == 1:
                return owned_game_ids
            elif type == 2:
                return owned_game_names
        
        elif installed == 1:
        
            local_games = []
            local_game_ids = []
            local_game_names = []
            local_game_sizes = []
            
            local_games_command = subprocess.Popen('"'+legendary_location+'\legendary.exe" list-installed', stdout=subprocess.PIPE, shell=True)
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
        
            if type == 0:
                return local_games
            elif type == 1:
                return local_game_ids
            elif type == 2:
                return local_game_names
            elif type == 3:
                logger.info(local_game_sizes)
                return local_game_sizes
                
        elif installed == 2:
        
            owned_gameslist = self.generate_gamelist(0,1)
            installed_gameslist = self.generate_gamelist(1,1)
            uninstalled_gameslist = []
            
            for i in range(len(owned_gameslist)):
                if not owned_gameslist[i] in installed_gameslist:
                    uninstalled_gameslist.append(LocalGame(owned_gameslist[i],0))
                    
            return uninstalled_gameslist    

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
    async def get_owned_games(self):
        return self.generate_gamelist(0,0)
    '''
    async def prepare_os_compatibility_context(self, game_ids) -> t.Set[AppName]:
        mac_items = set()
        for it in await self._epic_client.get_library_items(platform=LibraryPlatform.Mac):
            mac_items.add(it.app_name)
        return mac_items

    async def get_os_compatibility(self, game_id, context) -> OSCompatibility:
        if game_id in context:
            return OSCompatibility.MacOS | OSCompatibility.Windows
        if game_id in self._owned_games_cache:
            return OSCompatibility.Windows
        logger.warning('OSCompatibility: game_id not found in cache')
        return None
    ''''''
    async def prepare_game_times_context(self, game_ids) -> t.Optional[t.Dict[str, str]]:
        if len(game_ids) > 1:
            return await self._epic_client.get_playtime_all()
        return {
            game_ids[0]: await self._epic_client.get_playtime(game_ids[0])
        }
        
    async def get_game_time(self, game_id, context: t.Dict[str, str]):
        total_played_time = round(int(context.get(game_id, 0)) / 60)
        return GameTime(game_id, total_played_time, last_played_time=None)

    async def get_friends(self) -> t.List[UserInfo]:
        ids: t.List[Friend] = await self._epic_client.get_friends()
        chunk_size = 100
        requests = [
            self._epic_client.get_users_info(ids[x: x + chunk_size])
            for x in range(0, len(ids), chunk_size)
        ]
        user_infos = []
        for friends in await asyncio.gather(*requests):
            for friend in friends:
                user_infos.append(UserInfo(friend.account_id, friend.display_name, None, None))
        return user_infos
    '''    
    async def get_local_games(self):
        return self.generate_gamelist(1,0)
    '''    
    async def prepare_local_size_context(self, game_ids) -> t.Dict[AppName, GameManifest]:
        return parse_manifests()
    '''    
    async def get_local_size(self, game_id, context):
        local_game_sizes = self.generate_gamelist(1,3) 
        
        for i in range(len(local_game_sizes)):
            if game_id == local_game_sizes[i][0]:
                install_size = local_game_sizes[i][1]
        
                install_size = int(float(install_size)*1000000000)
                logger.info(game_id)
                logger.info(install_size)     
                return install_size
    '''       
    async def _open_epic_browser(self):
        url = "https://www.epicgames.com/store/download"
        logger.info(f"Opening Epic website {url}")
        webbrowser.open(url)
    '''
    async def launch_game(self, game_id):
        #os.system('"G:\Program Files (x86)\Legendary\legendary.exe" launch ' + game_id)
        if "false" not in update_check.lower():
            os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" update '+game_id+'"')
        os.system('"'+legendary_location+'\legendary.exe" launch ' + game_id + launch_flags)

    def _is_game_installed(self, game_id):
        
        local_game_ids = self.generate_gamelist(1,1)
        
        if game_id in local_game_ids:
            return True
        else:
            return False
            

    async def install_game(self, game_id):
        os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" install '+game_id+'"')

    async def uninstall_game(self, game_id):
        os.system('start cmd.exe /c ""'+legendary_location+'\legendary.exe" uninstall '+game_id+'"')
    '''    
    async def _check_for_new_games(self):
        await asyncio.sleep(600)
        refreshed_owned_games = await self._get_owned_games()
        for app_name in refreshed_owned_games:
            if app_name not in self._owned_games_cache:
                title = refreshed_owned_games[app_name]
                self.add_game(Game(app_name, title, None, LicenseInfo(LicenseType.SinglePurchase)))
                self._owned_games_cache[app_name] = title           
    def _update_local_game_statuses(self):
        updated = self._local_provider.consume_updated_games()
        for id_ in updated:
            new_state = self._local_provider.games[id_]
            self.update_local_game_status(LocalGame(id_, new_state))
    ''''''
    def tick(self):
        
        #owned_gameslist = self.generate_gamelist(0,0)
        #owned_gamesnamelist = self.generate_gamelist(0,2)
        
        changed = False
        local_gameslist = self.generate_gamelist(1,0)
        
        for i in range(len(local_gameslist)):
            if local_gameslist[i] not in self._local_game_cache:
                self.update_local_game_status(LocalGame(local_gameslist[i], 1))
                changed = True
        
        for i in range(len(self._local_game_cache)):
            if self._local_game_cache[i] not in local_gameslist:
                self.update_local_game_status(LocalGame(self._local_game_cache[i], 0))
                changed = True
        
        if changed:
            self.local_game_cache = local_gameslist
        for i in range(len(owned_gameslist)):
            if owned_gameslist[i] not in self._owned_game_cache:
                new_game = Game(
                    game_id=owned_gameslist[i],
                    game_title=owned_gamesnamelist[i],
                    dlcs=[],
                    license_info=LicenseInfo(LicenseType.SinglePurchase)
                )
                self.add_game(new_game)
    '''
    async def shutdown_platform_client(self):
        await self._local_client.shutdown_platform_client()

    async def shutdown(self):
        if self._http_client:
            await self._http_client.close()


def main():
    create_and_run_plugin(EpicPlugin, sys.argv)


if __name__ == "__main__":
    main()
