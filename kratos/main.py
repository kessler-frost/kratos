from agno.agent import Agent
from agno.models.ollama import Ollama
from typing import Optional, List
from microvm import bootstrap, invoke_agent, cleanup_agent
import cloudpickle


def submit(agent: Agent, name: str, dependencies: Optional[List[str]] = None) -> str:
    """
    Submit an ephemeral agent for deployment (Lambda-style).
    
    Args:
        agent: The Agno agent to deploy as ephemeral container
        name: Unique name for the ephemeral agent deployment
        dependencies: Optional list of additional Python packages
        
    Returns:
        Ephemeral deployment identifier/status
    """
    try:
        bootstrap(name, cloudpickle.dumps(agent), dependencies)
        return f"Ephemeral agent deployed: {name}"
    except Exception as e:
        return f"Failed to deploy ephemeral agent '{name}': {e}"


def invoke(name: str, instruction: str) -> str:
    """
    Invoke an ephemeral agent with instructions (Lambda-style).
    
    Args:
        name: Name of the ephemeral agent
        instruction: Instructions to send to the ephemeral agent
        
    Returns:
        Ephemeral agent response
    """
    try:
        return invoke_agent(name, instruction)
    except Exception as e:
        return f"Failed to invoke ephemeral agent '{name}': {e}"


def remove(name: str) -> str:
    """
    Destroy an ephemeral agent (Lambda-style cleanup).
    
    Args:
        name: Name of the ephemeral agent to destroy
        
    Returns:
        Destruction status
    """
    try:
        cleanup_agent(name)
        return f"Ephemeral agent '{name}' destroyed"
    except Exception as e:
        return f"Failed to destroy ephemeral agent '{name}': {e}"


def create_simple_agent() -> Agent:
    """Create a simple Agno agent with Ollama and a small model."""
    # Use a small model (will be pulled during bootstrap if needed)
    model = Ollama(id="llama3.2:1b")
    
    return Agent(
        model=model,
        name="SimpleAgent",
        description="A simple agent that can answer questions and help with tasks.",
        instructions="You are a helpful assistant. Keep your responses concise and clear."
    )


if __name__ == "__main__":
    agent_name = "ephemeral-agent"
    
    # Create and deploy ephemeral agent
    agent = create_simple_agent()
    print(f"🚀 {submit(agent, agent_name)}")
    
    # Test ephemeral agent invocations
    test_instructions = [
        "What is 2+2?",
        "Tell me a short joke.",
        "What is the capital of France?"
    ]
    
    for instruction in test_instructions:
        print(f"\n❓ {instruction}")
        print(f"🤖 {invoke(agent_name, instruction)}")
    
    # Destroy ephemeral agent
    print(f"\n💥 {remove(agent_name)}")
