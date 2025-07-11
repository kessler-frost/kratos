from agno.agent import Agent
from agno.models.lmstudio import LMStudio
from agno.tools.duckduckgo import DuckDuckGoTools
from sandbox import bootstrap, invoke_agent, cleanup_agent
import cloudpickle
from typing import Iterator, Optional, List
import time


def submit(agent: Agent, name: str, dependencies: Optional[List[str]] = None) -> str:
    """Deploy an agent."""
    try:
        bootstrap(name, cloudpickle.dumps(agent), dependencies)
        return f"Agent deployed: {name}"
    except Exception as e:
        return f"Failed: {e}"


def invoke(name: str, task: str) -> Iterator[str]:
    """Run a task on an agent and yield results as they come."""
    try:
        for response in invoke_agent(name, task):
            yield response
    except Exception as e:
        yield f"Failed: {e}"


def remove(name: str) -> str:
    """Remove an agent."""
    try:
        cleanup_agent(name)
        return f"Agent {name} removed"
    except Exception as e:
        return f"Failed: {e}"


if __name__ == "__main__":

    print("🚀 Kratos: Serverless Intelligence Platform")
    print("=" * 45)

    # Create and deploy a single test agent
    print("🔄 Building and submitting test agent...")

    test_agent = Agent(
        model=LMStudio(
            id="qwen/qwen3-4b",
            base_url="http://host.docker.internal:1234/v1",
        ),
        name="KratosWebSearch",
        tools=[DuckDuckGoTools()],
        instructions="You are Kratos Web Search Agent, specialized in finding current information from the web. Use DuckDuckGo to search for the latest news, facts, and information. Always provide up-to-date and accurate information from reliable sources. Be concise and focus on delivering the most relevant search results.",
        show_tool_calls=False,
    )
    print(f"🚀 {submit(test_agent, 'test-agent', dependencies=['ddgs', 'duckduckgo-search'])}")

    # Test single execution
    print("\n" + "="*50)
    print("🧪 Testing Agent Execution")
    print("="*50)

    task = "Hello, please introduce yourself and tell me what you can do."
    print(f"⚡ Task: {task}")
    print("💬 Response:")

    # Measure execution time
    start_time = time.time()

    for response_chunk in invoke('test-agent', task):
        print(response_chunk, end='', flush=True)

    end_time = time.time()
    execution_time = end_time - start_time

    print(f"\n\n⏱️  Execution time: {execution_time:.2f} seconds")

    # Cleanup the agent
    print("\n" + "="*50)
    print("💰 Cleaning up agent...")
    print(f"🗑️ {remove('test-agent')}")
