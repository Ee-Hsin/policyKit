"""Compatibility entry point for the greenfield data seed."""

import asyncio

from app.scripts.seed_data import seed_database

if __name__ == "__main__":
    asyncio.run(seed_database())
