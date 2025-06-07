"""API client for 3DTracking."""
import logging
import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp
from async_timeout import timeout

from .const import API_AUTH_URL, API_POSITIONS_URL

_LOGGER = logging.getLogger(__name__)

class ThreeDTrackingApiClientError(Exception):
    """Base exception for 3DTracking API client."""

class ThreeDTrackingAuthError(ThreeDTrackingApiClientError):
    """Exception for authentication errors."""

class ThreeDTrackingApiClient:
    """Client for the 3DTracking API."""

    def __init__(self, session: aiohttp.ClientSession, username, password):
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self._user_id_guid = None
        self._session_id = None
        self._session_expires = None # datetime object when session expires

    async def async_authenticate(self):
        """Authenticate with the 3DTracking API."""
        params = {
            "UserName": self._username,
            "Password": self._password,
        }
        _LOGGER.debug("Authenticating with 3DTracking API")
        try:
            async with timeout(10): # 10 seconds timeout
                response = await self._session.get(API_AUTH_URL, params=params)
                response.raise_for_status()
                data = await response.json()

            if data.get("Status", {}).get("Result") != "ok":
                error_message = data.get("Status", {}).get("Message", "Unknown authentication error")
                _LOGGER.error("3DTracking authentication failed: %s", error_message)
                raise ThreeDTrackingAuthError(error_message)

            result = data.get("Result")
            if not result:
                raise ThreeDTrackingAuthError("Authentication response missing 'Result' data.")

            self._user_id_guid = result.get("UserIdGuid")
            self._session_id = result.get("SessionId")
            # Session expires in 24 hours
            self._session_expires = datetime.now() + timedelta(hours=23, minutes=50) # Give a small buffer
            _LOGGER.debug("Successfully authenticated with 3DTracking API. Session expires at %s", self._session_expires)

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error during 3DTracking authentication: %s", err)
            raise ThreeDTrackingApiClientError(f"Network or timeout error during authentication: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error during 3DTracking authentication: %s", err)
            raise ThreeDTrackingApiClientError(f"Unexpected error during authentication: {err}") from err


    async def _ensure_authenticated(self):
        """Ensure the client is authenticated, refreshing token if needed."""
        if not self._session_id or (self._session_expires and datetime.now() >= self._session_expires):
            _LOGGER.debug("Session expired or not present, re-authenticating.")
            await self.async_authenticate()

    async def async_get_latest_positions(self):
        """Get the latest positions of all vehicles."""
        await self._ensure_authenticated()

        params = {
            "UserIdGuid": self._user_id_guid,
            "SessionId": self._session_id,
        }
        last_date_received_utc = datetime.now(timezone.utc) - timedelta(days=30)
        params["LastDateReceivedUtc"] = last_date_received_utc.strftime("%d %b %Y %H:%M:%S")

        _LOGGER.debug("Requesting latest positions from 3DTracking API")
        try:
            async with timeout(15): # 15 seconds timeout for data retrieval
                response = await self._session.get(API_POSITIONS_URL, params=params)
                response.raise_for_status()
                data = await response.json()

            if data.get("Status", {}).get("Result") != "ok":
                error_message = data.get("Status", {}).get("Message", "Unknown error getting positions")
                _LOGGER.error("3DTracking get positions failed: %s", error_message)
                # If it's an auth-related error, force re-authentication next time
                if "session" in error_message.lower() or "authentication" in error_message.lower():
                     self._session_id = None # Invalidate session to force re-auth
                raise ThreeDTrackingApiClientError(error_message)

            return data.get("Result", []) # Returns a list of unit dictionaries

        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error retrieving 3DTracking positions: %s", err)
            raise ThreeDTrackingApiClientError(f"Network or timeout error getting positions: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error retrieving 3DTracking positions: %s", err)
            raise ThreeDTrackingApiClientError(f"Unexpected error getting positions: {err}") from err