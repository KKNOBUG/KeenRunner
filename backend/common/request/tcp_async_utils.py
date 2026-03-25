# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : Krun
@Module  : tcp_async_utils
@DateTime: 2026/3/24 09:50
"""
import asyncio
import json
import random
from datetime import timedelta
from typing import Dict, Any


class AsyncTcpUtils:

    def __init__(
            self,
            host: str,
            port: int,
            *,
            length: int = 8,
            retries: int = 3,
            buffer_size: int = 1024,
            auto_reconnect: bool = False,
            timeout: timedelta = timedelta(seconds=30),
            **kwargs
    ):
        self.host = host
        self.port = port
        self.length = length
        self.retries = retries
        self.buffer_size = buffer_size
        self.auto_reconnect = auto_reconnect
        self.timeout = timeout
        self.kwargs = kwargs
        self.reader = None
        self.writer = None
        self.connected = False

    async def __aenter__(self):
        await self._connection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _connection(self):
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=self.host,
                    port=self.port,
                ), timeout=self.timeout.total_seconds()
            )
            self.connected = True
        except asyncio.Timeout:
            if self.auto_reconnect and self.retries > 0:
                await self._reconnection()
        except Exception as e:
            ...

    async def _reconnection(self):
        self.retries -= 1
        await asyncio.sleep(random.randint(1, 3))
        await self._connection()

    async def send(self, data: str):
        if self.writer and self.connected:
            length_str = str(len(data)).zfill(self.length)
            self.writer.write(length_str.encode("utf-8") + data.encode("utf-8"))
            await self.writer.drain()
        else:
            if self.auto_reconnect:
                await self._reconnection()

    async def receive_headers(self):
        headers: Dict[str, Any] = {}
        if self.reader and self.connected:
            while True:
                line = await self.reader.readline()
                if line == b"\r\n":
                    break
                header, value = line.decode("utf-8").strip().split(": ")
                headers[header] = value
            return headers
        else:
            if self.auto_reconnect:
                await self._reconnection()
            return headers

    async def receive(self):
        if self.reader and self.connected:
            length_data = await self.reader.readexactly(self.length)
            length = int(length_data.decode("utf-8").strip())
            data = await self.reader.readexactly(length)
            return json.loads(data.decode("utf-8").strip())
        else:
            if self.auto_reconnect:
                await self._reconnection()
            return {"data": ""}

    async def close(self):
        try:
            if self.writer and self.connected:
                self.writer.close()
                await self.writer.wait_closed()
                self.connected = False
        except Exception as e:
            raise


async def main(host: str, port: int, data: Dict):
    async with AsyncTcpUtils(
            host=host,
            port=port
    ) as content:
        json_str = json.dumps(data)
        await content.send(json_str)
        response = await content.receive()
        return response


if __name__ == '__main__':
    rs = asyncio.run(main(host="", port=1, data={}))
