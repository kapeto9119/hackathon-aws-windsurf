#!/usr/bin/env python3
"""
Script to create the initial database migration
"""
import asyncio
import subprocess
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_migration():
    """
    Create the initial database migration
    """
    # Run alembic revision command
    subprocess.run(
        ["alembic", "revision", "--autogenerate", "-m", "Initial migration"],
        check=True
    )
    print("Migration created successfully!")

if __name__ == "__main__":
    asyncio.run(create_migration())
