import asyncio
import sys
from typing import List, Tuple


SCRIPTS_TO_RUN: List[Tuple[str, List[str]]] = [
    ("pracuj_pl.py", []),
    ("praca_pl.py", []),
    ("script2.py", ["--flag", "value"]) # Runs script2.py with "--flag value"
]

async def run_script(script: str, args: List[str]):
    """Runs a Python script asynchronously with arguments."""
    command = [sys.executable, script] + args
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        print(f"✅ {script} ran successfully!")
        print(stdout.decode().strip())
    else:
        print(f"❌ Error running {script}")
        print(stderr.decode().strip())

async def main():
    """Runs all scripts asynchronously."""
    tasks = [run_script(script, args) for script, args in SCRIPTS_TO_RUN]
    await asyncio.gather(*tasks)  # Run all scripts in parallel

if __name__ == "__main__":
    asyncio.run(main())  # Start async execution
