# Using docker for now, but this can be easily replaced with a microvm library.
# Apple's Containers actually use microvms under the hood but a release for the latest MacOS is not available yet.

import docker
from typing import Optional, List
import subprocess


client = docker.from_env()
BASE_IMAGE_NAME = "kratos-agent-base"


def _ensure_base_image_exists():
    """Build the base image if it doesn't exist"""
    try:
        client.images.get(BASE_IMAGE_NAME)
        print(f"Base image {BASE_IMAGE_NAME} already exists")
    except docker.errors.ImageNotFound:  # pyright: ignore
        print(f"Building base image {BASE_IMAGE_NAME}...")
        # Build the image from the Dockerfile in the current directory
        client.images.build(path=".", tag=BASE_IMAGE_NAME, rm=True)
        print(f"Base image {BASE_IMAGE_NAME} built successfully")


def bootstrap(name: str, serialized_agent: bytes, dependencies: Optional[List[str]] = None) -> None:
    
    # Ensure base image exists
    _ensure_base_image_exists()
    
    # Clean up any existing container with the same name
    try:
        existing_container = client.containers.get(name)
        existing_container.stop()
        existing_container.remove()
    except docker.errors.NotFound:  # pyright: ignore
        pass  # Container doesn't exist, which is fine
    
    # Create container from base image (don't start yet)
    container = client.containers.create(name=name, image=BASE_IMAGE_NAME, command="serve", detach=True)
    container.start()
    
    # Install additional dependencies if specified
    if dependencies:
        deps_str = " ".join(dependencies)
        res = container.exec_run(["/bin/bash", "-c", f"uv add {deps_str}"], workdir="/workdir")
        if res.exit_code != 0:
            print("Failed to add additional dependencies:", res.output)
    
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
    Run the agent with the given instructions in the existing container.
    Streams the output from the agent as it generates.
    This is designed to be called multiple times after bootstrap (Lambda-style).
    """
    # Get the container by name
    container = client.containers.get(name)
    
    # Start the container if it's not running
    if container.status != 'running':
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
    
    # Keep the container running for future invocations (Lambda-style)
    # Don't stop the container here
    
    # Return the complete output
    return full_output


def cleanup_agent(name: str) -> None:
    """
    Stop and remove the agent container.
    Call this when you're done with the agent to free up resources.
    """
    try:
        container = client.containers.get(name)
        container.stop()
        container.remove()
        print(f"Agent container {name} cleaned up successfully")
    except docker.errors.NotFound:  # pyright: ignore
        print(f"Agent container {name} not found")
