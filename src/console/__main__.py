"""Entry point de la consola: python -m src.console"""
import asyncio

from src.console.app import run_console

if __name__ == "__main__":
    asyncio.run(run_console())
