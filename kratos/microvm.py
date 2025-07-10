# Using docker for now, but this can be easily replaced with a microvm library.
# Apple's Containers actually use microvms under the hood but a release for the latest MacOS is not available yet.

import base64
import docker
from typing import Optional, List


client = docker.from_env()
BASE_IMAGE_NAME = "kratos-agent-base"
AGENT_FILE_PATH = "/agent.pkl"
WORKDIR = "/workdir"


def _ensure_base_image_exists() -> None:
    """Build the base image if it doesn't exist."""
    try:
        client.images.get(BASE_IMAGE_NAME)
        print(f"Base image {BASE_IMAGE_NAME} already exists")
    except docker.errors.ImageNotFound:  # pyright: ignore
        print(f"Building base image {BASE_IMAGE_NAME}...")
        try:
            client.images.build(path=".", tag=BASE_IMAGE_NAME, rm=True)
            print(f"Base image {BASE_IMAGE_NAME} built successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to build base image: {e}") from e


def _exec_command(container, command: str, workdir: str = WORKDIR) -> None:
    """Execute a command in the container and raise on failure."""
    result = container.exec_run(["/bin/bash", "-c", command], workdir=workdir)
    if result.exit_code != 0:
        raise RuntimeError(f"Command failed: {command}\nOutput: {result.output}")


def bootstrap(name: str, serialized_agent: bytes, dependencies: Optional[List[str]] = None) -> None:
    """
    Bootstrap an agent container with the given name and serialized agent.
    
    Args:
        name: Unique name for the agent container
        serialized_agent: Cloudpickle-serialized agent object
        dependencies: Optional list of additional Python packages to install
        
    Raises:
        RuntimeError: If container creation, dependency installation, or agent setup fails
    """
    
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
    try:
        container = client.containers.create(name=name, image=BASE_IMAGE_NAME, command="serve", detach=True)
        container.start()
    except Exception as e:
        raise RuntimeError(f"Failed to create or start container: {e}") from e
    
    # Install additional dependencies if specified
    if dependencies:
        deps_str = " ".join(dependencies)
        _exec_command(container, f"uv add {deps_str}")
    
    # Create agent.pkl file with the serialized agent
    # Write the serialized agent to a file using base64 encoding to handle binary data
    encoded_agent = base64.b64encode(serialized_agent).decode('utf-8')
    _exec_command(container, f'echo "{encoded_agent}" | base64 -d > {AGENT_FILE_PATH}', workdir="/")
    
    # Stop the container
    container.stop()


def run_agent(name: str, instructions: str) -> str:
    """
    Run the agent with the given instructions in the existing container.
    
    Args:
        name: Name of the agent container (must be bootstrapped first)
        instructions: Instructions to pass to the agent
        
    Returns:
        Complete output from the agent execution
        
    Raises:
        RuntimeError: If container is not found or execution fails
        
    Note:
        This is designed to be called multiple times after bootstrap (Lambda-style).
        The container stays running between calls for performance.
    """
    try:
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
with open('{AGENT_FILE_PATH}', 'rb') as f:
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
        result = container.exec_run(["/bin/bash", "-c", f'/root/.local/bin/uv run python -c "{python_script}"'], workdir=WORKDIR, stream=True)
    except docker.errors.NotFound:  # pyright: ignore
        raise RuntimeError(f"Agent container '{name}' not found. Did you run bootstrap first?") from None
    except Exception as e:
        raise RuntimeError(f"Failed to run agent: {e}") from e
    
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
    
    Args:
        name: Name of the agent container to cleanup
        
    Raises:
        RuntimeError: If cleanup fails (container not found is handled gracefully)
        
    Note:
        Call this when you're done with the agent to free up resources.
    """
    try:
        container = client.containers.get(name)
        container.stop()
        container.remove()
        print(f"Agent container {name} cleaned up successfully")
    except docker.errors.NotFound:  # pyright: ignore
        print(f"Agent container {name} not found")
    except Exception as e:
        raise RuntimeError(f"Failed during cleanup of container {name}: {e}") from e
