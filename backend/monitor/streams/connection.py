"""Base WebSocket connection with automatic reconnection and heartbeat."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.protocol import State as WsState

logger = logging.getLogger(__name__)


class BaseWebSocketStream(ABC):
    """Base class for Upstox WebSocket streams with reconnection.

    Provides:
    - Automatic reconnection with exponential backoff (1s -> 2s -> 4s ... max)
    - Message parsing via abstract _parse_message()
    - Hook for post-connect setup (_on_connected)
    - Clean start/stop lifecycle
    """

    def __init__(
        self,
        name: str,
        get_auth_url: Callable[[], Coroutine[Any, Any, str]],
        on_message: Callable[[Any], Coroutine[Any, Any, None]],
        max_reconnect_delay: float = 60.0,
        heartbeat_timeout: float = 30.0,
    ):
        self.name = name
        self._get_auth_url = get_auth_url
        self._on_message = on_message
        self._max_reconnect_delay = max_reconnect_delay
        self._heartbeat_timeout = heartbeat_timeout
        self._ws: ClientConnection | None = None
        self._running = False
        self._reconnect_delay = 1.0
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the WebSocket connection loop."""
        if self._running:
            logger.warning(f"[{self.name}] Already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[{self.name}] Stream started")

    async def stop(self):
        """Gracefully stop the connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info(f"[{self.name}] Stream stopped")

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._ws.state is WsState.OPEN

    async def _run_loop(self):
        """Main connection loop with exponential backoff reconnection."""
        while self._running:
            try:
                url = await self._get_auth_url()
                logger.info(f"[{self.name}] Connecting to {url[:80]}...")

                async with websockets.connect(
                    url, ping_interval=20, ping_timeout=10
                ) as ws:
                    self._ws = ws
                    self._reconnect_delay = 1.0  # Reset on successful connect
                    logger.info(f"[{self.name}] Connected")
                    await self._on_connected(ws)
                    await self._receive_loop(ws)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                logger.warning(
                    f"[{self.name}] Connection error: {e}. "
                    f"Reconnecting in {self._reconnect_delay:.0f}s..."
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )

        self._ws = None

    async def _receive_loop(self, ws: ClientConnection):
        """Receive and dispatch messages."""
        async for message in ws:
            try:
                parsed = self._parse_message(message)
                if parsed is not None:
                    await self._on_message(parsed)
            except Exception as e:
                logger.error(f"[{self.name}] Error processing message: {e}")

    async def _on_connected(self, ws: ClientConnection):
        """Called after connection established. Override for subscriptions."""
        pass

    @abstractmethod
    def _parse_message(self, raw: bytes | str) -> Any | None:
        """Parse raw WebSocket message. Return None to skip."""
        ...

    async def send(self, data: bytes | str):
        """Send a message on the WebSocket."""
        if self._ws and self._ws.state is WsState.OPEN:
            await self._ws.send(data)
        else:
            logger.warning(f"[{self.name}] Cannot send — not connected")
