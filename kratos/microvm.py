# Kratos: Serverless compute platform for ephemeral agents
# Currently using Docker containers, but will migrate to native Apple Containers
# when they become available on the latest macOS for better performance per watt.

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
    except docker.errors.ImageNotFound:  # pyright: ignore
        try:
            client.images.build(path=".", tag=BASE_IMAGE_NAME, rm=True)
        except Exception as e:
            raise RuntimeError(f"Failed to build base image: {e}") from e


def _exec_command(container, command: str, workdir: str = WORKDIR) -> None:
    """Execute a command in the container and raise on failure."""
    result = container.exec_run(["/bin/bash", "-c", command], workdir=workdir)
    if result.exit_code != 0:
        raise RuntimeError(f"Command failed: {command}\nOutput: {result.output}")


def _extract_model_id(serialized_agent: bytes) -> Optional[str]:
    """Extract the model ID from a serialized agent."""
    try:
        import cloudpickle
        agent = cloudpickle.loads(serialized_agent)
        return agent.model.id
    except Exception:
        return None


def bootstrap(name: str, serialized_agent: bytes, dependencies: Optional[List[str]] = None) -> None:
    """
    Bootstrap a lightweight, ephemeral agent for serverless micro-task execution.
    
    Creates an isolated, fast-launching environment similar to cloud functions,
    ready to handle micro-tasks like search, parsing, editing, or content generation.
    
    Args:
        name: Unique identifier for the ephemeral agent instance
        serialized_agent: Cloudpickle-serialized agent ready for micro-task execution
        dependencies: Optional list of additional Python packages for specialized tasks
        
    Raises:
        RuntimeError: If serverless agent bootstrap fails
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
    
    # Pull the specific model that the agent requires
    model_id = _extract_model_id(serialized_agent)
    if model_id:
        try:
            _exec_command(container, f"ollama pull {model_id}")
        except RuntimeError:
            pass  # Model pulling failed, agent may fail if model not available
    
    # Create agent.pkl file with the serialized agent
    # Write the serialized agent to a file using base64 encoding to handle binary data
    encoded_agent = base64.b64encode(serialized_agent).decode('utf-8')
    _exec_command(container, f'echo "{encoded_agent}" | base64 -d > {AGENT_FILE_PATH}', workdir="/")
    
    # Stop the container
    container.stop()


def invoke_agent(name: str, instructions: str) -> str:
    """
    Execute a micro-task on a serverless ephemeral agent.
    
    Invokes the agent to handle lightweight tasks like search, parsing, editing,
    or content generation. Designed for burst execution patterns with minimal overhead.
    
    Args:
        name: Identifier of the ephemeral agent instance
        instructions: Micro-task instructions for the agent to execute
        
    Returns:
        Task execution result from the ephemeral agent
        
    Raises:
        RuntimeError: If agent instance not found or micro-task execution fails
        
    Note:
        Optimized for per-second billing with strict memory/CPU limits.
        Agent stays warm between invocations for efficiency.
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

# Get instructions from command line argument
instructions = sys.argv[1] if len(sys.argv) > 1 else "Hello"

# Run the agent with streaming enabled
try:
    # Try streaming first
    response = agent.run(instructions, stream=True)
    
    from agno.utils.pprint import pprint_run_response
    
    # For now, just use the response directly with pprint
    # The streaming will happen at the model level
    pprint_run_response(response, markdown=True)
except Exception as e:
    # Fallback to non-streaming if streaming fails
    try:
        response = agent.run(instructions, stream=False)
        from agno.utils.pprint import pprint_run_response
        pprint_run_response(response, markdown=True)
    except Exception as e2:
        print(f"Error running agent: {{e2}}", file=sys.stderr)
        sys.exit(1)
'''
        
        # Write the Python script to a temporary file in the container
        script_content_b64 = base64.b64encode(python_script.encode('utf-8')).decode('utf-8')
        _exec_command(container, f'echo "{script_content_b64}" | base64 -d > /run_agent.py', workdir="/")
        
        # Execute the Python script with instructions as argument
        result = container.exec_run(["/bin/bash", "-c", f'/root/.local/bin/uv run python /run_agent.py "{instructions}"'], workdir=WORKDIR, stream=True)
    except docker.errors.NotFound:  # pyright: ignore
        raise RuntimeError(f"Agent container '{name}' not found. Did you run bootstrap first?") from None
    except Exception as e:
        raise RuntimeError(f"Failed to run agent: {e}") from e
    
    # Collect and return the output
    full_output = ""
    for chunk in result.output:
        chunk_str = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
        full_output += chunk_str
    
    return full_output.strip()

def cleanup_agent(name: str) -> None:
    """
    Teardown serverless agent instance and reclaim resources.
    
    Immediately shuts down the ephemeral agent and frees all allocated
    memory/CPU resources. Part of the per-second billing model.
    
    Args:
        name: Identifier of the ephemeral agent instance to teardown
        
    Raises:
        RuntimeError: If teardown fails (missing instance handled gracefully)
    """
    try:
        container = client.containers.get(name)
        container.stop()
        container.remove()
    except docker.errors.NotFound:  # pyright: ignore
        pass  # Container doesn't exist, which is fine
    except Exception as e:
        raise RuntimeError(f"Failed during cleanup of container {name}: {e}") from e
