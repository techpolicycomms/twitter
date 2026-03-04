#!/usr/bin/env python3
"""Initialize the RegWatch database (create all tables)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db


async def main():
    print("Creating RegWatch database tables...")
    await init_db()
    print("Done. Tables created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
