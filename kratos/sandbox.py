import asyncio
from microsandbox import PythonSandbox
from sh import msb  # pyright: ignore

msb.pull("microsandbox/python")

async def main():
    async with PythonSandbox.create(name="my-sandbox") as sb:
        with open("install.py", "r") as f:
            exec = await sb.run(f.read())
        print(await exec.output())

asyncio.run(main())