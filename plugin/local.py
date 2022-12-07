import os
import sys
import abc
import asyncio
import subprocess
import json
import logging
import typing as t
from collections import defaultdict
from json.decoder import JSONDecodeError

from galaxy.api.types import LocalGameState
from galaxy.api.errors import FailedParsingManifest

from process_watcher import ProcessWatcher

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"

if WIN:
    import winreg

if WIN:
    _program_data = os.getenv("PROGRAMDATA", "")
elif MAC:
    _program_data = os.path.expanduser("~/Library/Application Support")
else:
    raise NotImplementedError("Unsupported OS")


logger = logging.getLogger(__name__)


GameManifest = t.NewType("GameManifest", dict)
ThirdPartyAppManifest = t.NewType("ThirdPartyAppManifest", dict)
InstallLocation = t.NewType("InstallLocation", str)
AppName = str


def get_manifests_path():
    return os.path.join(_program_data, "Epic", "EpicGamesLauncher", "Data", "Manifests")


def get_third_party_manifests_path():
    path = os.path.join(_program_data, "Epic", "EpicGamesLauncher", "Data", "ThirPartyManagedApps")
    # just in case of fixed typo in directory name in the future
    path_alt = os.path.join(_program_data, "Epic", "EpicGamesLauncher", "Data", "ThirdPartyManagedApps")
    for p in [path, path_alt]:
        if os.path.exists(p):
            return p
    return path


def get_launcher_installed_path():
    return os.path.join(_program_data, "Epic", "UnrealEngineLauncher", "LauncherInstalled.dat")


def parse_manifests() -> t.Dict[AppName, GameManifest]:
    manifests = {}
    manifests_path = get_manifests_path()
    for item in os.listdir(manifests_path):
        item_path = os.path.join(manifests_path, item)
        if os.path.splitext(item_path)[1] == ".item":
            with open(item_path, "r") as f:
                manifest = json.load(f)
                manifests[manifest["AppName"]] = GameManifest(manifest)
    return manifests


def get_third_party_game_location_windows(manifest: ThirdPartyAppManifest) -> t.Optional[InstallLocation]:
    """Returns InstallLocation or None if app is not installed"""
    try:
        registry_path, registry_key = manifest["RegistryPath"], manifest["RegistryKey"]
    except KeyError:
        raise FailedParsingManifest(f"Unknown manifest structure: {manifest}")

    try:
        reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        with winreg.OpenKey(reg, registry_path) as path:
            location = winreg.QueryValueEx(path, registry_key)[0]
    except OSError:
        return None

    if os.path.exists(location):
        return InstallLocation(location)
    else:
        return None


def get_third_party_game_location_dummy(manifest: ThirdPartyAppManifest) -> t.Optional[InstallLocation]:
    return None


class ThirdPartyAppsParser:
    def __init__(
        self,
        get_location: t.Callable[[ThirdPartyAppManifest], t.Optional[InstallLocation]],
    ):
        self._path = get_third_party_manifests_path()
        self._get_location_impl = get_location
        self._manifests_stats: t.Dict[str, os.stat_result] = dict()
        self._manifests: t.Dict[AppName, ThirdPartyAppManifest] = dict()

    @property
    def manifests(self) -> t.Dict[AppName, ThirdPartyAppManifest]:
        """Returns all already parsed manifests (requires `update` beforehand)"""
        return self._manifests

    @staticmethod
    def _load_manifest(manifest_path: str) -> ThirdPartyAppManifest:
        with open(manifest_path, "r") as f:
            content = f.read()
            try:
                return ThirdPartyAppManifest(json.loads(content))
            except (FileNotFoundError, JSONDecodeError) as e:
                raise FailedParsingManifest(content) from e

    @staticmethod
    def _load_manifests(
        manifest_paths: t.Iterable[str],
    ) -> t.Dict[AppName, ThirdPartyAppManifest]:
        """Parse all manifests."""
        manifests = {}
        for path in manifest_paths:
            try:
                manifest = ThirdPartyAppsParser._load_manifest(path)
            except FailedParsingManifest as e:
                logger.error(f"Error while parsing {path}: {e}. Content: {e.data}")
            else:
                manifests[manifest["AppName"]] = manifest
        return manifests

    @staticmethod
    def _get_manifests_stats(path) -> t.Dict[str, os.stat_result]:
        stats = {}
        try:
            file_list = os.listdir(path)
        except FileNotFoundError:
            file_list = []
        for filename in file_list:
            full_path = os.path.join(path, filename)
            try:
                stats[full_path] = os.stat(full_path)
            except FileNotFoundError:  # removed meanwhile
                continue
        return stats

    def update(self):
        """Reparses manifests if any change."""
        new_stats = self._get_manifests_stats(self._path)
        if new_stats != self._manifests_stats:
            self._manifests_stats = new_stats
            self._manifests = self._load_manifests(new_stats.keys())

    def get_installed_apps(self) -> t.Dict[AppName, InstallLocation]:
        """Gets installed third party games from already parsed manifests (requires `update` beforehand)"""
        installed: t.Dict[AppName, InstallLocation] = {}
        for app_name, manifest in self._manifests.items():
            install_location = self._get_location_impl(manifest)
            if install_location is not None:
                installed[app_name] = install_location
        return installed


class LauncherInstalledParser:
    def __init__(self):
        self._path = get_launcher_installed_path()
        self._last_modified: t.Optional[float] = None

    def file_has_changed(self) -> bool:
        try:
            stat = os.stat(self._path)
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.exception(f"Stating {self._path} has failed: {str(e)}")
            raise RuntimeError("Stating failed:" + str(e))
        else:
            if stat.st_mtime != self._last_modified:
                self._last_modified = stat.st_mtime
                return True
            return False

    def _load_file(self):
        content = {}
        try:
            with open(self._path, "rb") as f:
                content = json.loads(f.read())
        except FileNotFoundError as e:
            logger.warning(str(e))
        except JSONDecodeError as e:
            logger.error("Error during decoding JSON file: `%s`, with error: `%s`" % (self._path, str(e)))
        return content

    def parse(self) -> t.Dict[AppName, InstallLocation]:
        installed_games = {}
        content = self._load_file()
        game_list = content.get("InstallationList", [])
        for entry in game_list:
            app_name = entry.get("AppName", None)
            if not app_name or app_name.startswith("UE"):
                continue
            installed_games[entry["AppName"]] = InstallLocation(entry["InstallLocation"])
        return installed_games


class LocalGamesProvider:
    def __init__(self, luncher_process_identifier: str, get_third_party_game_location: t.Callable):
        self._games: t.DefaultDict[str, LocalGameState] = defaultdict(lambda: LocalGameState.None_)
        self._updated_games: t.Set[AppName] = set()
        self._first_run = True
        self._status_updater = None

        self._parser = LauncherInstalledParser()
        self._installed_games: t.Dict[AppName, InstallLocation] = dict()

        self._third_party_parser = ThirdPartyAppsParser(get_third_party_game_location)
        self._third_party_installed_games: t.Dict[AppName, InstallLocation] = dict()

        self._ps_watcher = ProcessWatcher(luncher_process_identifier)
        self._running_games: t.Set[AppName] = set()

    @property
    def first_run(self):
        return self._first_run

    @property
    def games(self):
        return self._games

    def is_third_party_game(self, game_id: AppName) -> bool:
        """Assumption: there is no shared AppName's between third party and first party."""
        self._third_party_parser.update()
        return game_id in self._third_party_parser.manifests

    async def search_process(self, game_id, timeout):
        await self._ps_watcher.pool_until_game_start(game_id, timeout, sint=0.5, lint=2)

    def is_game_running(self, game_id):
        return self._ps_watcher._is_app_tracked_and_running(game_id)

    def consume_updated_games(self):
        updated_games = self._updated_games.copy()
        self._updated_games.clear()
        return updated_games

    async def setup(self):
        logger.info("Running local games provider setup")
        self._check_for_installed()
        if self._parse_processes_needed:
            await self._ps_watcher.parse_processes_tree(interval=0.01)
        self._check_for_running()
        self._status_updater = asyncio.create_task(self._endless_status_checker())
        self._first_run = False

    @property
    async def _parse_processes_needed(self):
        if not self._installed_games:
            return False
        if self._running_games:
            return False
        return True

    async def _endless_status_checker(self):
        logger.info("Starting endless status checker")
        counter = 0
        while True:
            try:
                self._check_for_installed()
                self._check_for_third_party_installed()
                self._check_for_running(check_for_new=(counter % 7 == 0))
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(repr(e))
            finally:
                counter += 1
                await asyncio.sleep(1)

    def _check_for_third_party_installed(self):
        self._third_party_parser.update()
        installed = self._third_party_parser.get_installed_apps()
        self._update_game_statuses(
            set(self._third_party_installed_games),
            set(installed),
            LocalGameState.Installed,
        )
        self._third_party_installed_games = installed

    def _check_for_installed(self):
        if not self._parser.file_has_changed():
            return
        installed = self._parser.parse()
        self._update_game_statuses(set(self._installed_games), set(installed), LocalGameState.Installed)
        self._installed_games = installed

    def _check_for_running(self, check_for_new=False):
        """Requires checking for installed games beforehand"""
        self._ps_watcher.watched_games = {
            **self._third_party_installed_games,
            **self._installed_games,
        }
        running = self._ps_watcher.get_running_games(check_under_launcher=check_for_new)
        self._update_game_statuses(self._running_games, running, LocalGameState.Running)
        self._running_games = running

    def _update_game_statuses(self, previous, current, status):
        for id_ in current - previous:
            self._games[id_] |= status
            if not self._first_run:
                self._updated_games.add(id_)

        for id_ in previous - current:
            self._games[id_] ^= status
            if not self._first_run:
                self._updated_games.add(id_)


class ClientNotInstalled(Exception):
    pass


class _Launcher(abc.ABC):
    @abc.abstractproperty
    def launcher_process_identifier(self) -> str:
        pass

    @abc.abstractproperty
    def is_installed(self):
        pass

    @abc.abstractmethod
    def exec(self):
        pass

    @abc.abstractmethod
    def shutdown_platform_client(self):
        pass


class _MacosLauncher(_Launcher):
    _OPEN = "open"
    _DEFAULT_INSTALL_LOCATION = "/Applications/Epic Games Launcher.app"
    _LAUNCHER_PROCESS_IDENTIFIER = "Epic Games Launcher"

    def __init__(self):
        self._was_client_installed = None

    @property
    def launcher_process_identifier(self):
        return self._LAUNCHER_PROCESS_IDENTIFIER

    @property
    def is_installed(self):
        """:returns:     bool or None if not known """
        # in case we have tried to run it previously
        if self._was_client_installed is not None:
            return self._was_client_installed

        # else we assume that is installed under /Applications
        if os.path.exists(self._DEFAULT_INSTALL_LOCATION):
            return True
        else:  # probably not but we don't know for sure
            return None

    async def exec(self, cmd, prefix_cmd=True):
        if prefix_cmd:
            cmd = f"{self._OPEN} {cmd}"
        logger.info(f"Executing shell command: {cmd}")
        proc = await asyncio.create_subprocess_shell(cmd)
        status = None
        try:
            status = await asyncio.wait_for(proc.wait(), timeout=2)
        except asyncio.TimeoutError:
            logger.warning("Calling Epic Launcher timeouted. Probably fresh installed w/o executable permissions.")
        else:
            if status != 0:
                logger.debug(f"Calling Epic Launcher failed with code {status}. Assuming it is not installed")
                self._was_client_installed = False
                raise ClientNotInstalled
            else:
                self._was_client_installed = True

    async def shutdown_platform_client(self):
        await self.exec("osascript -e 'quit app \"Epic Games Launcher\"'", prefix_cmd=False)


class _WindowsLauncher(_Launcher):
    _OPEN = "start"
    _WINREG_INSTALL_LOCATION = R"com.epicgames.launcher\shell\open\command"
    _LAUNCHER_PROCESS_IDENTIFIER = "EpicGamesLauncher.exe"

    @property
    def launcher_process_identifier(self):
        return self._LAUNCHER_PROCESS_IDENTIFIER

    @staticmethod
    def _parse_winreg_path(path):
        return path.replace('"', "").partition("%")[0].strip()

    @property
    def is_installed(self):
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_CLASSES_ROOT)
            with winreg.OpenKey(reg, self._WINREG_INSTALL_LOCATION) as key:
                path = self._parse_winreg_path(winreg.QueryValueEx(key, "")[0])
            return os.path.exists(path)
        except OSError:
            return False

    async def exec(self, cmd, prefix_cmd=True):
        if not self.is_installed:
            raise ClientNotInstalled

        if prefix_cmd:
            cmd = f"{self._OPEN} {cmd}"
        logger.info(f"Executing shell command: {cmd}")
        subprocess.Popen(cmd, shell=True)

    async def shutdown_platform_client(self):
        await self.exec('taskkill.exe /im "EpicGamesLauncher.exe"', prefix_cmd=False)


local_client: _Launcher

if WIN:
    local_client = _WindowsLauncher()

    def get_third_party_game_location(manifest: ThirdPartyAppManifest) -> t.Optional[InstallLocation]:
        return get_third_party_game_location_windows(manifest)


elif MAC:
    local_client = _MacosLauncher()

    def get_third_party_game_location(manifest: ThirdPartyAppManifest) -> t.Optional[InstallLocation]:
        """No support for other OS - no third party non-Windows games so far"""
        return get_third_party_game_location_dummy(manifest)
