# Kratos: Serverless Intelligence Platform
# Currently using Docker containers, but will migrate to native Apple Containers
# when they become available on the latest macOS for better performance per watt.

import base64
import cloudpickle
import docker
import os
import tempfile
import time
import uuid
from typing import Optional, List, Iterator


# Configuration
client = docker.from_env()
AGENT_FILE_PATH = "/agent.pkl"
WORKDIR = "/workdir"
CONTAINER_EXECUTION_TIMEOUT = 300  # 5 minutes max for container execution
BUILD_TIMEOUT = 600  # 10 minutes max for image builds



def _exec_command(container, command: str, workdir: str = WORKDIR) -> None:
    """Execute a command in the container and raise on failure."""
    result = container.exec_run(["/bin/bash", "-c", command], workdir=workdir)
    if result.exit_code != 0:
        raise RuntimeError(f"Command failed: {command}\nOutput: {result.output}")


def _validate_agent_model(serialized_agent: bytes) -> tuple[bool, str]:
    """Validate agent model for Kratos requirements.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        agent = cloudpickle.loads(serialized_agent)
        
        # Check if model provider is LMStudio
        model_type = type(agent.model).__name__
        if model_type != 'LMStudio':
            return False, f"Kratos only supports LMStudio models for efficient local compute. Found: {model_type}"
        
        return True, ""
    except Exception as e:
        return False, f"Failed to validate agent model: {e}"


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
    
    # Clean up any existing image with the same name
    agent_image_name = f"kratos-agent-{name}"
    try:
        existing_image = client.images.get(agent_image_name)
        client.images.remove(existing_image.id, force=True)
    except docker.errors.ImageNotFound:  # pyright: ignore
        pass  # Image doesn't exist, which is fine
    
    # Build custom image with dependencies directly
    _build_agent_image(agent_image_name, serialized_agent, dependencies)


def _build_agent_image(image_name: str, serialized_agent: bytes, dependencies: Optional[List[str]] = None) -> None:
    """
    Build a custom Docker image with dependencies and model baked in.
    
    Args:
        image_name: Name for the custom image
        serialized_agent: Cloudpickle-serialized agent
        dependencies: Optional list of additional Python packages
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Read the Dockerfile template
        template_path = os.path.join(os.path.dirname(__file__), "Dockerfile.template")
        with open(template_path, 'r') as f:
            dockerfile_content = f.read()
        
        # Prepare additional dependencies installation command
        if dependencies:
            deps_str = " ".join(dependencies)
            dependencies_install = f"RUN uv add {deps_str}"
        else:
            dependencies_install = "# No additional dependencies"
        
        # Replace template placeholders
        dockerfile_content = dockerfile_content.replace("{{DEPENDENCIES_INSTALL}}", dependencies_install)
        
        # Write the customized Dockerfile
        dockerfile_path = os.path.join(temp_dir, "Dockerfile")
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)
        
        # Write the serialized agent to agent.pkl
        agent_path = os.path.join(temp_dir, "agent.pkl")
        with open(agent_path, 'wb') as f:
            f.write(serialized_agent)
        
        # Build the custom image with timeout
        try:
            client.images.build(path=temp_dir, tag=image_name, rm=True, timeout=BUILD_TIMEOUT)
        except Exception as e:
            raise RuntimeError(f"Failed to build agent image: {e}") from e


def invoke_agent(name: str, instructions: str) -> Iterator[str]:
    """
    Execute a micro-task on a serverless ephemeral agent.
    
    Creates a new ephemeral container for each invocation, runs the task, and cleans up.
    Designed for true serverless execution with no persistent state.
    
    Args:
        name: Identifier of the agent image to use
        instructions: Micro-task instructions for the agent to execute
        
    Yields:
        Task execution result chunks from the ephemeral agent as they are generated
        
    Raises:
        RuntimeError: If agent image not found or micro-task execution fails
        
    Note:
        Each invocation creates a fresh container that is automatically cleaned up.
    """
    # Create ephemeral container from the custom agent image
    agent_image_name = f"kratos-agent-{name}"
    container = None
    
    try:
        # Generate unique container name for this invocation
        container_name = f"kratos-invoke-{name}-{uuid.uuid4().hex[:4]}"
        
        # Create and start ephemeral container
        try:
            container = client.containers.create(
                name=container_name, 
                image=agent_image_name, 
                command=["sleep", "infinity"],  # Keep container running for script execution
                detach=True
            )
            container.start()
        except docker.errors.ImageNotFound:  # pyright: ignore
            raise RuntimeError(f"Agent image '{agent_image_name}' not found. Please bootstrap the agent first.")
        
        # Create a Python script to unpickle and run the agent with streaming
        python_script = f'''
import cloudpickle
import sys

# Load the agent from the pickle file
with open('/workdir/agent.pkl', 'rb') as f:
    agent = cloudpickle.load(f)

# Get instructions from command line argument
instructions = sys.argv[1] if len(sys.argv) > 1 else "Hello"

# Run the agent with streaming enabled
try:
    response = agent.run(instructions, stream=True)
    
    # Handle streaming response properly
    if hasattr(response, '__iter__') and not isinstance(response, str):
        # Streaming response - print chunks as they come
        for chunk in response:
            if hasattr(chunk, 'content') and chunk.content:
                print(chunk.content, end='', flush=True)
            elif hasattr(chunk, 'text') and chunk.text:
                print(chunk.text, end='', flush=True)
            elif isinstance(chunk, str):
                print(chunk, end='', flush=True)
            else:
                print(str(chunk), end='', flush=True)
    else:
        # Non-streaming response
        if hasattr(response, 'content'):
            print(response.content, end='', flush=True)
        else:
            print(response, end='', flush=True)
except Exception as e:
    print(f"Error running agent: {{e}}", file=sys.stderr)
    sys.exit(1)
'''
        
        # Write the Python script to a temporary file in the container
        script_content_b64 = base64.b64encode(python_script.encode('utf-8')).decode('utf-8')
        _exec_command(container, f'echo "{script_content_b64}" | base64 -d > /run_agent.py', workdir="/")
        
        start_time = time.time()
        
        # Execute with streaming
        exec_result = container.exec_run(["/bin/bash", "-c", f'/usr/local/bin/uv run python /run_agent.py "{instructions}"'], workdir=WORKDIR, stream=True)
        
        # Yield output chunks as they come with timeout enforcement
        for chunk in exec_result.output:
            # Check if we've exceeded the timeout
            if time.time() - start_time > CONTAINER_EXECUTION_TIMEOUT:
                # Kill the container if it's taking too long
                try:
                    container.kill()
                except:
                    pass
                raise RuntimeError(f"Container execution timeout exceeded ({CONTAINER_EXECUTION_TIMEOUT} seconds)")
            
            chunk_str = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
            if chunk_str.strip():  # Only yield non-empty chunks
                yield chunk_str
                
    except docker.errors.NotFound:  # pyright: ignore
        raise RuntimeError(f"Agent image '{agent_image_name}' not found. Did you run bootstrap first?") from None
    except Exception as e:
        raise RuntimeError(f"Failed to run agent: {e}") from e
    finally:
        # Always clean up the ephemeral container
        if container:
            try:
                container.stop()
                container.remove()
            except Exception:
                pass  # Ignore cleanup errors

def cleanup_agent(name: str) -> None:
    """
    Clean up agent image and any remaining containers for a specific agent.
    
    Removes the agent's custom image and any leftover containers that might
    exist from failed invocations.
    
    Args:
        name: Identifier of the agent to clean up
        
    Raises:
        RuntimeError: If cleanup fails
    """
    try:
        # Clean up any remaining containers for this agent
        containers = client.containers.list(all=True)
        agent_containers = [c for c in containers if c.name.startswith(f'kratos-invoke-{name}-')]
        
        for container in agent_containers:
            try:
                container.stop()
                container.remove()
            except Exception:
                pass  # Ignore individual container cleanup errors
        
        # Remove the agent's custom image
        agent_image_name = f"kratos-agent-{name}"
        try:
            image = client.images.get(agent_image_name)
            client.images.remove(image.id, force=True)
        except docker.errors.ImageNotFound:  # pyright: ignore
            pass  # Image doesn't exist, which is fine
        except Exception as e:
            raise RuntimeError(f"Failed to remove agent image {agent_image_name}: {e}") from e
            
    except Exception as e:
        raise RuntimeError(f"Failed during cleanup of agent {name}: {e}") from e


def prune() -> None:
    """
    Clean up all Kratos-related containers and images.
    
    Removes all containers and images created by Kratos to free up system resources.
    This includes:
    - All kratos-agent-* images
    - All kratos-invoke-* containers (ephemeral execution containers)
    
    Raises:
        RuntimeError: If cleanup fails
    """
    try:
        # Remove all Kratos containers (both running and stopped)
        containers = client.containers.list(all=True)
        kratos_containers = [c for c in containers if c.name.startswith('kratos-')]
        
        for container in kratos_containers:
            try:
                container.stop()
                container.remove()
            except Exception:
                pass  # Ignore individual container cleanup errors
        
        # Remove all Kratos images
        images = client.images.list()
        kratos_images = []
        
        for image in images:
            if image.tags:
                for tag in image.tags:
                    if tag.startswith('kratos-'):
                        kratos_images.append(image)
                        break
        
        for image in kratos_images:
            try:
                client.images.remove(image.id, force=True)
            except Exception:
                pass  # Ignore individual image cleanup errors
            
    except Exception as e:
        raise RuntimeError(f"Failed to prune Kratos resources: {e}") from e
