# start.py
import asyncio
import sys
import signal
from pyrogram import errors

from bot import app  # import the app object (no start on import)

RETRY_DELAY = 3  # seconds
MAX_RETRIES = None  # None => retry forever


async def safe_start():
    retries = 0
    while True:
        try:
            await app.start()
            print("🚀 Science Quiz Bot is running...")
            break
        except (RuntimeError, errors.RPCError) as e:
            # common issues: time sync / network / auth problems
            retries += 1
            print(f"⏳ Start failed (attempt {retries}): {e}", file=sys.stderr)
            if MAX_RETRIES and retries >= MAX_RETRIES:
                print("❌ Max retries reached, exiting.", file=sys.stderr)
                raise
            await asyncio.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"❌ Unexpected error while starting: {e}", file=sys.stderr)
            await asyncio.sleep(RETRY_DELAY)


async def main():
    await safe_start()

    # keep running until stopped
    stop_event = asyncio.Event()

    def _signal_handler(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # windows or environment that doesn't support add_signal_handler
            pass

    print("Press Ctrl+C to stop.")
    await stop_event.wait()

    print("Stopping bot...")
    await app.stop()
    print("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())