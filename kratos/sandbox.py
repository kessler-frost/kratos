from microsandbox import PythonSandbox
from sh import msb  # pyright: ignore
import random
import string

# generate a random string of 4 characters
def generate_random_string(length: int):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


async def bootstrap_vm(prefix: str):
    msb.pull("microsandbox/python")

    async with PythonSandbox.create(name=f"{prefix}-{generate_random_string(4)}") as sb:
        with open("bootstrap_script.py", "r") as f:
            exec = await sb.run(f.read())
        print(await exec.output())