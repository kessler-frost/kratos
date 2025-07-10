# Kratos: Serverless Intelligence Platform
# Currently using Docker containers, but will migrate to native Apple Containers
# when they become available on the latest macOS for better performance per watt.

import base64
import docker
from typing import Optional, List, Iterator


# Configuration
client = docker.from_env()
BASE_IMAGE_NAME = "kratos-agent-base"
AGENT_FILE_PATH = "/agent.pkl"
WORKDIR = "/workdir"
MODEL_SIZE_LIMIT_GB = 6.0
MODEL_PULL_TIMEOUT = 30


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


def _validate_agent_model(serialized_agent: bytes) -> tuple[bool, str]:
    """Validate agent model for Kratos requirements.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        import cloudpickle
        agent = cloudpickle.loads(serialized_agent)
        
        # Check if model provider is Ollama
        model_type = type(agent.model).__name__
        if model_type != 'Ollama':
            return False, f"Kratos only supports Ollama models for efficient local compute. Found: {model_type}"
        
        return True, ""
    except Exception as e:
        return False, f"Failed to validate agent model: {e}"


def _check_model_size(model_id: str, container) -> tuple[bool, str]:
    """Check if model size is within Kratos limits (< 6GB).
    
    Pulls the model and checks its actual size for efficiency and optimization.
    
    Returns:
        tuple: (is_valid, error_message_or_size)
    """
    try:
        # Pull the model to get accurate size information (with timeout for large models)
        pull_result = container.exec_run(["/bin/bash", "-c", f"timeout {MODEL_PULL_TIMEOUT}s ollama pull {model_id}"])
        if pull_result.exit_code != 0:
            pull_output = pull_result.output.decode() if pull_result.output else ""
            if "timeout" in pull_output.lower() or pull_result.exit_code == 124:
                return False, f"Model {model_id} pull timed out (likely >{MODEL_SIZE_LIMIT_GB}GB). Kratos supports models ≤{MODEL_SIZE_LIMIT_GB}GB for efficiency and optimization."
            elif "not found" in pull_output.lower():
                return False, f"Model {model_id} not found in Ollama registry."
            else:
                return False, f"Failed to pull model {model_id}: {pull_output}"
        
        # Get the actual model size using ollama show
        result = container.exec_run(["/bin/bash", "-c", f"ollama show {model_id} | grep -i 'size\\|parameters' || ollama list | grep '{model_id}'"])
        
        if result.exit_code == 0:
            output = result.output.decode().strip()
            
            # Try to extract size from ollama list output (more reliable)
            list_result = container.exec_run(["/bin/bash", "-c", f"ollama list | grep '{model_id}' | head -1"])
            if list_result.exit_code == 0:
                list_output = list_result.output.decode().strip()
                if list_output:
                    # Parse ollama list format: NAME    ID    SIZE    MODIFIED
                    parts = list_output.split()
                    if len(parts) >= 3:
                        size_str = parts[2]  # Third column is size
                        try:
                            size_gb = _parse_size_to_gb(size_str)
                            if size_gb > 6.0:
                                return False, f"Model {model_id} size ({size_str}) exceeds 6GB limit. Kratos supports models ≤6GB for efficiency and optimization."
                            else:
                                return True, f"Model size: {size_str}"
                        except ValueError:
                            # If we can't parse the size, allow it but warn
                            return True, f"Model size: {size_str} (format not recognized, proceeding)"
        
        # If we can't determine size, allow it but warn
        return True, "Model size: unknown (proceeding)"
        
    except Exception as e:
        return False, f"Failed to check model size: {e}"


def _parse_size_to_gb(size_str: str) -> float:
    """Parse size string to GB for comparison."""
    import re
    
    size_str = size_str.strip().upper()
    
    # Extract number and unit
    match = re.match(r'([0-9.]+)\s*([A-Z]*)', size_str)
    if not match:
        raise ValueError(f"Cannot parse size: {size_str}")
    
    value = float(match.group(1))
    unit = match.group(2) if match.group(2) else 'B'
    
    # Convert to GB
    if unit == 'GB':
        return value
    elif unit == 'MB':
        return value / 1024
    elif unit == 'KB':
        return value / (1024 * 1024)
    elif unit == 'B':
        return value / (1024 * 1024 * 1024)
    else:
        raise ValueError(f"Unknown unit: {unit}")


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
    
    # Validate agent model requirements for Kratos
    is_valid, error_msg = _validate_agent_model(serialized_agent)
    if not is_valid:
        raise RuntimeError(f"Agent validation failed: {error_msg}")
    
    # Ensure base image exists
    _ensure_base_image_exists()
    
    # Clean up any existing container with the same name
    try:
        existing_container = client.containers.get(name)
        existing_container.stop()
        existing_container.remove()
    except docker.errors.NotFound:  # pyright: ignore
        pass  # Container doesn't exist, which is fine
    
    # Create container from base image
    try:
        container = client.containers.create(name=name, image=BASE_IMAGE_NAME, command="serve", detach=True)
        container.start()
    except Exception as e:
        raise RuntimeError(f"Failed to create or start container: {e}") from e
    
    # Install additional dependencies if specified
    if dependencies:
        deps_str = " ".join(dependencies)
        _exec_command(container, f"uv add {deps_str}")
    
    # Validate and pull the specific model that the agent requires
    model_id = _extract_model_id(serialized_agent)
    if model_id:
        try:
            # Check model size before allowing deployment
            size_valid, size_msg = _check_model_size(model_id, container)
            if not size_valid:
                # Clean up container before failing
                container.stop()
                container.remove()
                raise RuntimeError(f"Model validation failed: {size_msg}")
        except RuntimeError:
            # Clean up container on any model-related failure
            try:
                container.stop()
                container.remove()
            except:
                pass
            raise
    
    # Create agent.pkl file with the serialized agent
    # Write the serialized agent to a file using base64 encoding to handle binary data
    encoded_agent = base64.b64encode(serialized_agent).decode('utf-8')
    _exec_command(container, f'echo "{encoded_agent}" | base64 -d > {AGENT_FILE_PATH}', workdir="/")
    
    # Stop the container
    container.stop()


def invoke_agent(name: str, instructions: str) -> Iterator[str]:
    """
    Execute a micro-task on a serverless ephemeral agent.
    
    Invokes the agent to handle lightweight tasks like search, parsing, editing,
    or content generation. Designed for burst execution patterns with minimal overhead.
    
    Args:
        name: Identifier of the ephemeral agent instance
        instructions: Micro-task instructions for the agent to execute
        
    Yields:
        Task execution result chunks from the ephemeral agent as they are generated
        
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
    response = agent.run(instructions, stream=True)
    
    # Handle streaming response properly
    if hasattr(response, '__iter__') and not isinstance(response, str):
        # Streaming response - collect all chunks to build complete content
        content_parts = []
        final_response = None
        
        for chunk in response:
            final_response = chunk
            if hasattr(chunk, 'content') and chunk.content:
                content_parts.append(chunk.content)
        
        # Print the complete content from all chunks
        if content_parts:
            print(''.join(content_parts))
        elif final_response and hasattr(final_response, 'content'):
            print(final_response.content)
        else:
            print(final_response)
    else:
        # Non-streaming response
        if hasattr(response, 'content'):
            print(response.content)
        else:
            print(response)
except Exception as e:
    print(f"Error running agent: {{e}}", file=sys.stderr)
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
    
    # Yield output chunks as they come
    for chunk in result.output:
        chunk_str = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
        if chunk_str.strip():  # Only yield non-empty chunks
            yield chunk_str

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
