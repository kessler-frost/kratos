# Using docker for now, but this can be easily replaced with a microvm library.
# Apple's Containers actually use microvms under the hood but a release for the latest MacOS is not available yet.

import docker
from typing import Optional, List
import tarfile
import io


client = docker.from_env()


def bootstrap(name: str, serialized_agent: bytes, dependencies: Optional[List[str]] = None) -> None:
    
    # Start the ollama container
    container = client.containers.create(name=name, image="ollama/ollama", command="serve", detach=True)
    container.start()
    
    # Install curl and upgrade packages
    container.exec_run("apt update && apt upgrade -y && apt install -y curl", workdir="/")
    
    # Install uv
    container.exec_run("curl -LsSf https://astral.sh/uv/install.sh | sh", workdir="/")
    
    # Add uv to PATH
    container.exec_run("echo 'export PATH=/root/.local/bin:$PATH' >> /root/.bashrc", workdir="/")
    
    # Initialize uv project
    container.exec_run("export PATH=/root/.local/bin:$PATH && uv init", workdir="/")
    
    # Install default dependencies from bootstrap.sh
    default_deps = ["ollama", "agno", "cloudpickle"]
    
    # Combine default dependencies with any additional ones passed
    all_deps = default_deps.copy()
    if dependencies:
        all_deps.extend(dependencies)
    
    # Install all dependencies
    deps_str = " ".join(all_deps)
    container.exec_run(f"export PATH=/root/.local/bin:$PATH && uv add {deps_str}", workdir="/")
    
    # Create agent.pkl file with the serialized agent
    # Create a tar archive in memory containing the agent.pkl file
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        agent_info = tarfile.TarInfo(name='agent.pkl')
        agent_info.size = len(serialized_agent)
        agent_data = io.BytesIO(serialized_agent)
        tar.addfile(agent_info, agent_data)
    
    tar_stream.seek(0)
    container.put_archive(path='/', data=tar_stream)
    
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
    result = container.exec_run(f'export PATH=/root/.local/bin:$PATH && uv run python -c "{python_script}"', workdir="/", stream=True)
    
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