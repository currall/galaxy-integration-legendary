import json
import enum
import aiohttp
import logging
import typing as t

from yarl import URL
from multidict import MultiDict
from galaxy.api.errors import UnknownBackendResponse
from collections import namedtuple


logger = logging.getLogger(__name__)

AccountId = str

LibraryItem = namedtuple('LibraryItem', ['namespace', 'app_name', 'title', 'type'])
Friend = namedtuple('Friend', ['account_id', 'display_name'])


class LibraryPlatform(enum.Enum):
    Windows = 'Windows'
    Mac = 'Mac'
    All = ''


API_HOST = URL.build(scheme='https', host='api.epicgames.dev')
LIBRARY_SERVICE = "epic/library/v1"
FRIENDS_SERVICE = "epic/friends/v1"
ACCOUNTS_SERVICE = "epic/id/v1"


class EpicClient:
    def __init__(self, http_client):
        self._http_client = http_client

    @property
    def _me(self):
        return self._http_client.account_id

    @staticmethod
    async def _parse_json(data: t.Union[str, aiohttp.ClientResponse]):
        try:
            if isinstance(data, aiohttp.ClientResponse):
                parsed = await data.json()
            else:
                parsed = json.loads(data)
            return parsed
        except (KeyError, aiohttp.ContentTypeError, json.JSONDecodeError) as e:
            logger.exception("Can not parse backend response")
            raise UnknownBackendResponse(repr(e))

    async def _get_payload(self, url):
        response = await self._http_client.get(url)
        return await self._parse_json(response)

    async def _get_paginated_records(self, url: t.Union[str, URL]) -> t.List[t.Any]:
        response = await self._http_client.get(str(url))
        records = (await self._parse_json(response))['records']
        meta = response.headers.get('x-epic-metadata')
        if meta:
            next_cursor = (await self._parse_json(meta)).get('nextCursor')
            if next_cursor:
                url = URL(url).update_query(cursor=next_cursor)
                records.extend(await self._get_paginated_records(url))
        return records

    async def get_playtime(self, artifact_id: str) -> t.Dict[str, int]:
        url = API_HOST / LIBRARY_SERVICE / f'playtime/account/{self._me}/artifact/{artifact_id}'
        response = await self._get_payload(url)
        try:
            return response['totalTime']
        except KeyError as e:
            raise UnknownBackendResponse(repr(e))

    async def get_playtime_all(self) -> t.Dict[str, int]:
        url = API_HOST / LIBRARY_SERVICE / f'playtime/account/{self._me}/all'
        response = await self._get_payload(url)
        try:
            return {
                game['artifactId']: game['totalTime']
                for game in response
            }
        except (TypeError, KeyError) as e:
            raise UnknownBackendResponse(repr(e))

    async def get_library_items(self, platform=LibraryPlatform.All) -> t.List[LibraryItem]:
        url = (
            API_HOST / LIBRARY_SERVICE / 'items'
        ).with_query(MultiDict([
            ("includeTitles", "true"),
            ("limit", 300),
            ("excludeNs", "ue")
        ]))
        if platform != LibraryPlatform.All:
            url = url.update_query([
                ("platform", platform.value),
            ])
        records = await self._get_paginated_records(url)
        try:
            return [
                LibraryItem(record['namespace'], record['appName'], record['title'], record['itemType'])
                for record in records
            ]
        except (TypeError, KeyError) as e:
            raise UnknownBackendResponse(repr(e))

    async def get_friends(self) -> t.List[AccountId]:
        url = API_HOST / FRIENDS_SERVICE / f'{self._me}/friends'
        try:
            return [friend['accountId'] for friend in await self._get_payload(url)]
        except KeyError as e:
            raise UnknownBackendResponse(repr(e))

    async def get_users_info(self, account_ids: t.Iterable[AccountId]) -> t.List[Friend]:
        """
        :param account_ids:     iterable with AccountId of at least one and not more than 100
        """
        url = (
            API_HOST / ACCOUNTS_SERVICE / 'accounts'
        ).with_query(MultiDict(
            [('accountId', aid) for aid in account_ids]
        ))
        try:
            return [
                Friend(fr['accountId'], fr['displayName'])
                for fr in await self._get_payload(url)
            ]
        except KeyError as e:
            raise UnknownBackendResponse(repr(e))
