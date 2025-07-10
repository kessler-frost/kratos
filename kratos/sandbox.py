from microsandbox import PythonSandbox
from sh import msb, msx  # pyright: ignore


async def bootstrap_vm(name: str):
    msb.pull("microsandbox/python")

    async with PythonSandbox.create(name=name) as sb:
        with open("bootstrap_script.py", "r") as f:
            exec = await sb.run(f.read())
        print(await exec.output())
    
import asyncio

asyncio.run(bootstrap_vm("my-sandbox"))

# def bootstrap_vm(name: str):
#     msb.pull("microsandbox/python")
#     with open("bootstrap_script.py", "r") as f:
#         text = f.read()
#         # text = "print('Hello, World!')"
#     print(f"Executing: {text}")
#     result = msx("python", "--", "-c", text)
#     print(f"Result: {result}")

# bootstrap_vm("my-sandbox")