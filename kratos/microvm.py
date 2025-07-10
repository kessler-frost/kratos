# Using docker for now, but this can be easily replaced with a microvm library.
# Apple's Containers actually use microvms under the hood but a release for the latest MacOS is not available yet.

import docker
from typing import Optional, List


client = docker.from_env()


def bootstrap(name: str, serialized_agent: bytes, dependencies: Optional[List[str]] = None) -> None:
    
    # Clean up any existing container with the same name
    try:
        existing_container = client.containers.get(name)
        existing_container.stop()
        existing_container.remove()
    except docker.errors.NotFound:  # pyright: ignore
        pass  # Container doesn't exist, which is fine
    
    # Start the ollama container
    container = client.containers.create(name=name, image="ollama/ollama", command="serve", detach=True)
    container.start()
    
    default_deps = ["ollama", "agno", "cloudpickle"]
    all_deps = default_deps.copy()
    if dependencies:
        all_deps.extend(dependencies)
    
    # Install all dependencies
    deps_str = " ".join(all_deps)

    # Create working directory first
    res = container.exec_run("mkdir -p /workdir")
    if res.exit_code != 0:
        print("Failed to create workdir:", res.output)

    # Install system dependencies
    res = container.exec_run(["/bin/bash", "-c", "apt update && apt upgrade -y && apt install -y curl"])
    if res.exit_code != 0:
        print("Failed to install system dependencies:", res.output)

    # Install uv
    res = container.exec_run(["/bin/bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"])
    if res.exit_code != 0:
        print("Failed to install uv:", res.output)

    # Initialize uv project in workdir
    res = container.exec_run(["/bin/bash", "-c", "/root/.local/bin/uv init"], workdir="/workdir")
    if res.exit_code != 0:
        print("Failed to initialize uv project:", res.output)

    # Add dependencies
    res = container.exec_run(["/bin/bash", "-c", f"/root/.local/bin/uv add {deps_str}"], workdir="/workdir")
    if res.exit_code != 0:
        print("Failed to add dependencies:", res.output)
    
    # Create agent.pkl file with the serialized agent
    # Write the serialized agent to a file using base64 encoding to handle binary data
    import base64
    encoded_agent = base64.b64encode(serialized_agent).decode('utf-8')
    
    # Create the agent.pkl file by decoding the base64 data
    res = container.exec_run(["/bin/bash", "-c", f'echo "{encoded_agent}" | base64 -d > /agent.pkl'])
    if res.exit_code != 0:
        print("Failed to create agent.pkl:", res.output)
    
    # Stop the container
    container.stop()


def run_agent(name: str, instructions: str) -> str:
    """
    Start the container and run the agent with the given instructions.
    Streams the output from the agent as it generates.
    """
    # Get the container by name
    container = client.containers.get(name)
    
    # Start the container
    container.start()
    
    # Create a Python script to unpickle and run the agent with streaming
    python_script = f'''
import cloudpickle
import sys

# Load the agent from the pickle file
with open('/agent.pkl', 'rb') as f:
    agent = cloudpickle.load(f)
    print(agent)

# Run the agent with streaming and collect the full response
# full_response = ""
# for chunk in agent.run("{instructions}", stream=True):
#     if hasattr(chunk, 'content') and chunk.content:
#         full_response += str(chunk.content)
#         # Print each chunk for real-time streaming
#         print(str(chunk.content), end='', flush=True)

# Print a final newline
print()
'''
    
    # Execute the Python script in the container and capture output
    result = container.exec_run(["/bin/bash", "-c", f'/root/.local/bin/uv run python -c "{python_script}"'], workdir="/workdir", stream=True)
    
    # Stream the output in real-time
    full_output = ""
    for chunk in result.output:
        chunk_str = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
        full_output += chunk_str
        # Yield each chunk for streaming to the caller
        print(chunk_str, end='', flush=True)
    
    # Stop the container after execution
    container.stop()
    
    # Return the complete output
    return full_output