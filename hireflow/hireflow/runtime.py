"""Small helper so async Semantic Kernel calls work from plain scripts AND Jupyter."""
import asyncio
from concurrent.futures import ThreadPoolExecutor


def run_sync(coro):
    """Run a coroutine to completion, even if an event loop is already running (notebooks)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
