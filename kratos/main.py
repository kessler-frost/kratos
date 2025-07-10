from agno.agent import Agent
from agno.models.ollama import Ollama
from typing import Optional, List
from microvm import bootstrap, invoke_agent, cleanup_agent
import cloudpickle


def submit(agent: Agent, name: str, dependencies: Optional[List[str]] = None) -> str:
    """
    Deploy a serverless agent for micro-task execution.
    
    Creates a lightweight, isolated environment optimized for burst workloads
    and per-second billing. Ideal for tasks like search, parsing, editing, and content generation.
    
    Args:
        agent: The agent configured for micro-task execution
        name: Unique identifier for the serverless agent instance
        dependencies: Optional packages for specialized micro-tasks
        
    Returns:
        Deployment status of the serverless agent
    """
    try:
        bootstrap(name, cloudpickle.dumps(agent), dependencies)
        return f"Serverless agent deployed: {name}"
    except Exception as e:
        return f"Failed to deploy serverless agent '{name}': {e}"


def invoke(name: str, instruction: str) -> str:
    """
    Execute a micro-task on a serverless agent.
    
    Designed for burst execution with per-second billing efficiency.
    Handles lightweight tasks with minimal overhead and strict resource limits.
    
    Args:
        name: Identifier of the serverless agent instance
        instruction: Micro-task instruction for execution
        
    Returns:
        Micro-task execution result
    """
    try:
        return invoke_agent(name, instruction)
    except Exception as e:
        return f"Failed to execute micro-task on agent '{name}': {e}"


def remove(name: str) -> str:
    """
    Teardown serverless agent and reclaim resources.
    
    Immediately frees all allocated memory/CPU resources as part of
    the per-second billing model. Ensures efficient resource utilization.
    
    Args:
        name: Identifier of the serverless agent to teardown
        
    Returns:
        Resource reclamation status
    """
    try:
        cleanup_agent(name)
        return f"Serverless agent '{name}' resources reclaimed"
    except Exception as e:
        return f"Failed to teardown agent '{name}': {e}"


def create_simple_agent() -> Agent:
    """Create a lightweight agent optimized for micro-task execution."""
    # Use a small, efficient model for fast inference and energy efficiency
    model = Ollama(id="llama3.2:1b")
    
    return Agent(
        model=model,
        name="MicroTaskAgent",
        description="Lightweight agent for serverless micro-tasks: search, parsing, editing, content generation.",
        instructions="You are an efficient micro-task agent. Provide concise, accurate responses optimized for quick execution."
    )


if __name__ == "__main__":
    agent_name = "micro-task-agent"
    
    # Deploy serverless agent for micro-task execution
    agent = create_simple_agent()
    print(f"🚀 {submit(agent, agent_name)}")
    
    # Execute burst of micro-tasks (typical Kratos workload)
    micro_tasks = [
        "What is 2+2?",
        "Generate a 3-word product name for a coffee app",
        "Extract the domain from: user@example.com"
    ]
    
    for task in micro_tasks:
        print(f"\n⚡ Micro-task: {task}")
        print(f"📊 Result: {invoke(agent_name, task)}")
    
    # Teardown and reclaim resources (per-second billing ends)
    print(f"\n💰 {remove(agent_name)}")
