import asyncio
import psutil
import logging
import time
from typing import Dict, Iterable, Set, Union
from dataclasses import dataclass


logger = logging.getLogger(__name__)

AppId = str
InstallLocation = str


@dataclass
class WatchedApp:
    """
    Application representation for purposes of watching its processes.
    Implements hash and comparison based on `id`.
    """
    id: AppId
    dir: InstallLocation
    is_game: bool = True

    def __eq__(self, other: Union['WatchedApp', AppId]):  # type: ignore
        if isinstance(other, WatchedApp):
            return self.id == other.id
        elif type(other) == AppId:
            return self.id == other
        else:
            raise TypeError(f"Trying to compare {type(self)} with {type(other)}")

    def __hash__(self):
        return hash(self.id)


class _ProcessWatcher:
    """Low level methods"""
    def __init__(self):
        self._watched_apps: Dict[WatchedApp, Set[psutil.Process]] = {}

    @property
    def watched_games(self) -> Dict[WatchedApp, Set[psutil.Process]]:
        return {k: v for k, v in self._watched_apps.items() if k.is_game}

    @watched_games.setter
    def watched_games(self, to_watch: Dict[AppId, InstallLocation]):
        # remove games not present in to_watch
        for app in list(self._watched_apps.keys()):
            if app.is_game and app.id not in to_watch:
                del self._watched_apps[app]
        # add games from to_watch keeping its processes if already present
        for game_id, path in to_watch.items():
            self._watched_apps.setdefault(WatchedApp(game_id, path), set())

    def _get_running_games(self) -> Set[AppId]:
        self.__remove_processes_if_dead()
        return set([game.id for game, procs in self.watched_games.items() if procs])

    def _is_app_tracked_and_running(self, app_id: AppId) -> bool:
        if app_id in self._watched_apps:
            for proc in self._watched_apps[app_id]:  # type: ignore[index]
                if proc.is_running:
                    return True
        return False

    def _search_in_all(self) -> None:
        """All processes check"""
        logger.info('Performing check for all processes')
        for proc in psutil.process_iter(ad_value=''):
            self.__match_process(proc)

    async def _search_in_all_slowly(self, interval: float = 0.02) -> None:
        """All processes check with async intervals; 0.02 usually lasts a few seconds"""
        logger.info(f'Performing async check in all processes; interval: {interval}')
        for proc in psutil.process_iter(ad_value=''):
            self.__match_process(proc)
            await asyncio.sleep(interval)

    def _search_in_children(self, processes: Iterable[psutil.Process], recursive=True) -> bool:
        """Search for running games processes under `processes` children and updates self._watched_apps.
        Returns True if any app was matched with at least one process."""
        found = False
        for proc in processes:
            try:
                for child in proc.children(recursive=recursive):
                    found |= self.__match_process(child)
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                logger.warning(f'Getting children of {proc} has failed: {e}')
        return found

    def __match_process(self, proc: psutil.Process) -> bool:
        for game in self._watched_apps:
            try:
                path = proc.exe()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            except FileNotFoundError:  # psutil#1738 for Mac
                pass
            else:
                if not path:
                    return False
                elif game.dir in path:
                    self._watched_apps[game].add(proc)
                    return True
        return False

    def __remove_processes_if_dead(self) -> None:
        for game, processes in self._watched_apps.items():
            # work on copy to avoid adding processes during iteration
            for proc in processes.copy():
                if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                    logger.debug(f'Process {proc} is dead')
                    self._watched_apps[game].remove(proc)


class ProcessWatcher(_ProcessWatcher):
    _LAUNCHER_ID = '__launcher__'

    def __init__(self, launcher_identifier: str):
        super().__init__()
        self._watched_apps[WatchedApp(self._LAUNCHER_ID, launcher_identifier, False)] = set()

    @property
    def _launcher_processes(self) -> Set[psutil.Process]:
        """Copy of current launcher processes"""
        return self._watched_apps[self._LAUNCHER_ID].copy()  # type: ignore[index]

    def _is_launcher_tracked_and_running(self) -> bool:
        """Cheap to perform"""
        return self._is_app_tracked_and_running(self._LAUNCHER_ID)

    def is_launcher_running(self) -> bool:
        """May be expensive to perform"""
        if self._is_launcher_tracked_and_running():
            return True
        self._search_in_all()
        return self._is_launcher_tracked_and_running()

    async def _pool_until_launcher_start(self, timeout: int, long_interval: float):
        start = time.time()
        while time.time() - start < timeout:
            if self._is_launcher_tracked_and_running():
                return True
            self._search_in_all()
            await asyncio.sleep(long_interval)
        return False

    async def parse_processes_tree(self, interval: float):
        """Parse all processses asynchronously waiting `interval` time after each process check."""
        await self._search_in_all_slowly(interval)

    async def pool_until_game_start(
            self,
            game_id: AppId,
            timeout: int,
            sint: float,
            lint: float
    ) -> bool:
        """
        :param sint     (short) interval between checking launcher children
        :param lint     (long) interval between checking if launcher exists
        :returns:       boolean if game process was found or not
        """
        logger.info(f'Starting wait for game {game_id} process')
        start = time.time()
        while time.time() - start < timeout:
            found = await self._pool_until_launcher_start(timeout, lint)
            if found:
                self._search_in_children(self._launcher_processes)
                if self._watched_apps[game_id]:  # type: ignore[index]
                    logger.debug(f'Game process for {game_id} found in {time.time() - start}s')
                    return True
                await asyncio.sleep(sint)

        self._search_in_all()
        if game_id in self._watched_apps:
            logger.debug('Game process found in the final fallback parsing all processes')
            return True
        return False

    def get_running_games(self, check_under_launcher: bool) -> Set[AppId]:
        """Return set of ids of currently running games.
        Note: does not actively look for launcher
        """
        if check_under_launcher and self._is_launcher_tracked_and_running():
            self._search_in_children(self._launcher_processes, recursive=True)
        return self._get_running_games()
