import asyncio
import time
from typing import Optional

class AsyncRateLimiter:
    def __init__(self, max_requests: int = 5, period: float = 1.0):
        self.max_requests: int = max_requests
        self.period: float = period
        self.request_count: int = 0
        self.last_reset: float = 0.0
        self.lock: asyncio.Lock = asyncio.Lock()

    async def allow_request(self) -> bool:
        async with self.lock:
            current_time: float = time.time()
            if self.request_count < self.max_requests and current_time - self.last_reset < self.period:
                self.request_count += 1
                return True
            elif current_time - self.last_reset >= self.period:
                self.request_count = 1
                self.last_reset = current_time
                return True
            else:
                return False

    async def block_request(self) -> None:
        async with self.lock:
            self.request_count = 0
            self.last_reset = time.time()

    async def __call__(self) -> bool:
        if self.request_count == 0:
            self.last_reset = time.time()
            self.request_count += 1
            return True
        return await self.allow_request()

async def main() -> None:
    limiter: AsyncRateLimiter = AsyncRateLimiter()
    for _ in range(10):
        if await limiter():
            print("Request allowed")
        else:
            print("Request blocked")
            await limiter.block_request()
        await asyncio.sleep(0.1)

asyncio.run(main())