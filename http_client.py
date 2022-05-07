import logging
import base64
import json
import typing as t
import asyncio

from galaxy.http import handle_exception, create_client_session
from galaxy.api.errors import AuthenticationRequired, AccessDenied


Credentials = t.Dict[str, str]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AuthenticatedHttpClient:
    def __init__(self, refresh_credentials_callback: t.Awaitable, auth_lost_callback: t.Callable):
        self._refresh_credentials_callback = refresh_credentials_callback
        self._auth_lost_callback = auth_lost_callback
        self._access_token = ''
        self._display_name = ''
        self._account_id = ''
        self._session = create_client_session()
        self._credentials_renewal_possible = asyncio.Event()
        self._credentials_renewal_possible.set()

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def is_authenticated(self) -> bool:
        return bool(self._access_token)

    @staticmethod
    def _decode_jwt(token):
        data = token.split('.')[1] + '=='
        decoded = base64.urlsafe_b64decode(data).decode('utf-8')
        return json.loads(decoded)

    def set_credentials(self, auth_data: Credentials):
        logger.info('Setting user credentials')
        self._access_token = auth_data['access_token']
        jwt = self._decode_jwt(self._access_token)
        self._account_id = jwt['sub']
        self._display_name = jwt['dn']

    async def _refresh_credentials(self):
        if self._credentials_renewal_possible.is_set():
            try:
                self._credentials_renewal_possible.clear()
                logger.info('Refreshing credentials')
                self.set_credentials(await self._refresh_credentials_callback())
            except AccessDenied:
                self._auth_lost('Refresh token invalid')
            finally:
                self._credentials_renewal_possible.set()
        await self._credentials_renewal_possible.wait()

    def _auth_lost(self, msg: str):
        self._access_token = ''
        self._auth_lost_callback()
        raise AuthenticationRequired(msg)

    async def _request(self, *args, **kwargs):
        with handle_exception():
            res = await self._session.request(*args, raise_for_status=False, **kwargs)
            logger.debug(f'{args[0]} <{args[1]}>: {res.status}, {await res.text()}')
            res.raise_for_status()
            return res

    async def _authorized_request(self, *args, repeated: int = 0, **kwargs):
        if not self.is_authenticated:
            raise AuthenticationRequired('Calling authorized_request without access_token')

        kwargs.setdefault("headers", {})["Authorization"] = f'bearer {self._access_token}'
        try:
            return await self._request(*args, **kwargs)
        except AuthenticationRequired:
            if repeated < 2:
                await self._refresh_credentials()
                return await self._authorized_request(*args, repeated=(repeated + 1), **kwargs)
            else:
                self._auth_lost('Fatal auth lost')

    async def get(self, *args, **kwargs):
        return await self._authorized_request('GET', *args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._authorized_request('POST', *args, **kwargs)

    async def close(self):
        await self._session.close()
