from agno.agent import Agent
from agno.models.ollama import Ollama
from microvm import bootstrap, invoke_agent, cleanup_agent
import cloudpickle


def submit(agent: Agent, name: str) -> str:
    """Deploy an agent."""
    try:
        bootstrap(name, cloudpickle.dumps(agent), None)
        return f"Agent deployed: {name}"
    except Exception as e:
        return f"Failed: {e}"


def invoke(name: str, task: str) -> str:
    """Run a task on an agent."""
    try:
        return invoke_agent(name, task)
    except Exception as e:
        return f"Failed: {e}"


def remove(name: str) -> str:
    """Remove an agent."""
    try:
        cleanup_agent(name)
        return f"Agent {name} removed"
    except Exception as e:
        return f"Failed: {e}"


def create_agent() -> Agent:
    """Create a Kratos agent."""
    return Agent(
        model=Ollama(id="llama3.2:1b"),
        name="KratosAgent",
        instructions="You are a helpful assistant. Be concise."
    )


if __name__ == "__main__":
    print("🚀 Kratos: Serverless Intelligence Platform")
    print("=" * 45)
    
    # Deploy
    agent = create_agent()
    print(f"🚀 {submit(agent, 'kratos')}")
    
    # Tasks
    tasks = ["What is 2+2?", "Email from: contact@example.com", "Coffee app name?"]
    for i, task in enumerate(tasks, 1):
        print(f"\n⚡ {i}: {task}")
        print(f"💬 {invoke('kratos', task)}")
    
    # Cleanup
    print(f"\n💰 {remove('kratos')}")
