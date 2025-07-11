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
BASE_IMAGE_NAME = "kratos-base"
AGENT_FILE_PATH = "/agent.pkl"
WORKDIR = "/workdir"
MODEL_SIZE_LIMIT_GB = 6.0
MODEL_PULL_TIMEOUT = 120  # 2 minutes max for model pulls
CONTAINER_EXECUTION_TIMEOUT = 300  # 5 minutes max for container execution
BUILD_TIMEOUT = 600  # 10 minutes max for image builds



def _ensure_optimized_base_image() -> None:
    """Build the optimized base image if it doesn't exist."""
    try:
        client.images.get(BASE_IMAGE_NAME)
    except docker.errors.ImageNotFound:  # pyright: ignore
        try:
            dockerfile_path = os.path.join(os.path.dirname(__file__), "Dockerfile.base")
            build_path = os.path.dirname(__file__)
            client.images.build(path=build_path, dockerfile=dockerfile_path, tag=BASE_IMAGE_NAME, rm=True, timeout=BUILD_TIMEOUT)
        except Exception as e:
            raise RuntimeError(f"Failed to build optimized base image: {e}") from e


def _exec_command(container, command: str, workdir: str = WORKDIR) -> None:
    """Execute a command in the container and raise on failure."""
    result = container.exec_run(["/bin/bash", "-c", command], workdir=workdir)
    if result.exit_code != 0:
        raise RuntimeError(f"Command failed: {command}\nOutput: {result.output}")


def _extract_model_id(serialized_agent: bytes) -> Optional[str]:
    """Extract the model ID from a serialized agent."""
    try:
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
        agent = cloudpickle.loads(serialized_agent)
        
        # Check if model provider is OpenAILike
        model_type = type(agent.model).__name__
        if model_type != 'OpenAILike':
            return False, f"Kratos only supports OpenAILike models for efficient local compute. Found: {model_type}"
        
        return True, ""
    except Exception as e:
        return False, f"Failed to validate agent model: {e}"


def _check_model_size(model_id: str, container) -> tuple[bool, str]:
    """Check if model is available for OpenAILike connection.
    
    For OpenAILike models, we don't need to pull or check size since they're accessed via API.
    
    Returns:
        tuple: (is_valid, success_message)
    """
    # For OpenAILike models, we don't need to check size as they're accessed via API
    return True, f"Model {model_id} configured for OpenAI-like API access"


# Size parsing function removed as it's no longer needed for OpenAILike models


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
    
    # Extract model ID for later use in the image build
    model_id = _extract_model_id(serialized_agent)
    
    # Clean up any existing image with the same name
    agent_image_name = f"kratos-agent-{name}"
    try:
        existing_image = client.images.get(agent_image_name)
        client.images.remove(existing_image.id, force=True)
    except docker.errors.ImageNotFound:  # pyright: ignore
        pass  # Image doesn't exist, which is fine
    
    # Ensure optimized base image exists
    _ensure_optimized_base_image()
    
    # Build custom image with dependencies and model baked in
    _build_agent_image(agent_image_name, serialized_agent, dependencies, model_id)


def _build_agent_image(image_name: str, serialized_agent: bytes, dependencies: Optional[List[str]] = None, model_id: Optional[str] = None) -> None:
    """
    Build a custom Docker image with dependencies and model baked in.
    
    Args:
        image_name: Name for the custom image
        serialized_agent: Cloudpickle-serialized agent
        dependencies: Optional list of additional Python packages
        model_id: Optional model ID to pull into the image
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Read the Dockerfile template
        template_path = os.path.join(os.path.dirname(__file__), "Dockerfile.template")
        with open(template_path, 'r') as f:
            dockerfile_content = f.read()
        
        # Prepare additional dependencies installation command (most common ones are pre-installed)
        if dependencies:
            # Filter out already installed dependencies
            common_deps = {"ddgs", "duckduckgo-search", "yfinance", "youtube-transcript-api"}
            additional_deps = [dep for dep in dependencies if dep not in common_deps]
            if additional_deps:
                deps_str = " ".join(additional_deps)
                dependencies_install = f"RUN uv add {deps_str}"
            else:
                dependencies_install = "# All dependencies already installed in base image"
        else:
            dependencies_install = "# No additional dependencies"
        
        # For OpenAILike models, no need to pull models locally
        model_pull = "# OpenAILike models are accessed via API, no local pulling needed"
        
        # Replace template placeholders
        dockerfile_content = dockerfile_content.replace("{{DEPENDENCIES_INSTALL}}", dependencies_install)
        dockerfile_content = dockerfile_content.replace("{{MODEL_PULL}}", model_pull)
        
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
    - The kratos-agent-base image
    
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
        
        # Also try to remove the optimized base image
        try:
            base_image = client.images.get(BASE_IMAGE_NAME)
            client.images.remove(base_image.id, force=True)
        except docker.errors.ImageNotFound:  # pyright: ignore
            pass  # Base image doesn't exist, which is fine
        except Exception:
            pass  # Ignore base image cleanup errors
            
    except Exception as e:
        raise RuntimeError(f"Failed to prune Kratos resources: {e}") from e
