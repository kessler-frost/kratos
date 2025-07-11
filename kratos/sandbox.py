# Kratos: Serverless Intelligence Platform
# Currently using Docker containers, but will migrate to native Apple Containers
# when they become available on the latest macOS for better performance per watt.

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
BUILD_TIMEOUT = 300  # 5 minutes max for image builds


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


def _extract_model_name(serialized_agent: bytes) -> str:
    """Extract the model name from a serialized agent.
    
    Returns:
        str: The model name or 'unknown' if extraction fails
    """
    try:
        agent = cloudpickle.loads(serialized_agent)
        return getattr(agent.model, 'id', 'unknown')
    except Exception:
        return 'unknown'


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
    
    # Extract model name for later use
    model_name = _extract_model_name(serialized_agent)
    
    # Clean up any existing image with the same name
    agent_image_name = f"kratos-agent-{name}"
    try:
        existing_image = client.images.get(agent_image_name)
        client.images.remove(existing_image.id, force=True)
    except docker.errors.ImageNotFound:  # pyright: ignore
        pass  # Image doesn't exist, which is fine
    
    # Build custom image with dependencies directly
    _build_agent_image(agent_image_name, serialized_agent, dependencies, model_name)


def _build_agent_image(image_name: str, serialized_agent: bytes, dependencies: Optional[List[str]] = None, model_name: str = "unknown") -> None:
    """
    Build a custom Docker image with dependencies and model baked in.
    
    Args:
        image_name: Name for the custom image
        serialized_agent: Cloudpickle-serialized agent
        dependencies: Optional list of additional Python packages
        model_name: Name of the model used by the agent
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
        dockerfile_content = dockerfile_content.replace("{{MODEL_NAME}}", model_name)
        
        # Write the customized Dockerfile
        dockerfile_path = os.path.join(temp_dir, "Dockerfile")
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)
        
        # Write the serialized agent to agent.pkl
        agent_path = os.path.join(temp_dir, "agent.pkl")
        with open(agent_path, 'wb') as f:
            f.write(serialized_agent)
        
        # Copy execute.py to the build context
        execute_py_source = os.path.join(os.path.dirname(__file__), "execute.py")
        execute_py_dest = os.path.join(temp_dir, "execute.py")
        with open(execute_py_source, 'r') as src, open(execute_py_dest, 'w') as dst:
            dst.write(src.read())
        
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
        
        # Get the model name from the image labels
        try:
            image = client.images.get(agent_image_name)
            model_name = image.labels.get('kratos.model_name', 'unknown')
        except Exception:
            model_name = "unknown"
        
        # Create and run ephemeral container with keyword arguments
        try:
            container = client.containers.run(
                image=agent_image_name,
                command=[
                    "--model_name", model_name,
                    "--container_name", container_name,
                    "--instructions", instructions
                ],
                name=container_name,
                detach=True,
                remove=False  # We'll remove it manually after getting the logs
            )
        except docker.errors.ImageNotFound:  # pyright: ignore
            raise RuntimeError(f"Agent image '{agent_image_name}' not found. Please bootstrap the agent first.")
        
        start_time = time.time()
        
        # Stream the container logs as they are generated
        for log_chunk in container.logs(stream=True, follow=True):
            # Check if we've exceeded the timeout
            if time.time() - start_time > CONTAINER_EXECUTION_TIMEOUT:
                # Kill the container if it's taking too long
                try:
                    container.kill()
                except:
                    pass
                raise RuntimeError(f"Container execution timeout exceeded ({CONTAINER_EXECUTION_TIMEOUT} seconds)")
            
            chunk_str = log_chunk.decode() if isinstance(log_chunk, bytes) else str(log_chunk)
            if chunk_str.strip():  # Only yield non-empty chunks
                yield chunk_str
        
        # Wait for container to finish and check exit code
        container.wait()
        result = container.attrs['State']
        if result['ExitCode'] != 0:
            error_logs = container.logs().decode()
            raise RuntimeError(f"Agent execution failed with exit code {result['ExitCode']}: {error_logs}")
                
    except docker.errors.NotFound:  # pyright: ignore
        raise RuntimeError(f"Agent image '{agent_image_name}' not found. Did you run bootstrap first?") from None
    except Exception as e:
        raise RuntimeError(f"Failed to run agent: {e}") from e
    finally:
        # Always clean up the ephemeral container
        if container:
            try:
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
