from agno.agent import Agent
from agno.models.lmstudio import LMStudio
from agno.tools.duckduckgo import DuckDuckGoTools
from sandbox import bootstrap, invoke_agent, cleanup_agent
import cloudpickle
from typing import Optional, List
import time
from concurrent.futures import ThreadPoolExecutor, wait


def submit(agent: Agent, name: str, dependencies: Optional[List[str]] = None) -> str:
    """Deploy an agent."""
    try:
        bootstrap(name, cloudpickle.dumps(agent), dependencies)
        return f"Agent deployed: {name}"
    except Exception as e:
        return f"Failed: {e}"


def invoke(name: str, task: str, print_stream: bool = True) -> None:
    """
    Run a task on an agent and handle printing internally.

    Be careful and disable print_stream if you are using a ThreadPoolExecutor.
    Otherwise, the output will be garbled.
    """
    try:
        for response in invoke_agent(name, task):
            if print_stream:
                print(response, end='', flush=True)
    except Exception as e:
        error_msg = f"Failed: {e}"
        if print_stream:
            print(error_msg, end='', flush=True)


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

    # Test concurrent execution with ThreadPoolExecutor
    print("\n" + "="*50)
    print("🧪 Testing Agent Execution")
    print("="*50)

    task = "Hello, please introduce yourself and tell me what you can do."
    print(f"⚡ Task: {task}")

    # Measure execution time
    start_time = time.time()

    # Run 3 concurrent agent invocations
    print(f"\n🚀 Starting 3 concurrent invocations at {time.strftime('%H:%M:%S')}")
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks at once with print_stream=True
        futures = [executor.submit(invoke, 'test-agent', task, False) for _ in range(3)]
        wait(futures)

    end_time = time.time()
    execution_time = end_time - start_time

    print(f"\n\n⏱️  Total execution time for 3 concurrent runs: {execution_time:.2f} seconds")
    print(f"📊 Average time per agent: {execution_time/3:.2f} seconds")
    print(f"🚀 Estimated sequential time would be: ~{execution_time*3:.2f} seconds")
    print(f"⚡ Speedup achieved: ~{(execution_time*3)/execution_time:.1f}x faster")

    # Cleanup the agent
    print("\n" + "="*50)
    print("💰 Cleaning up agent...")
    print(f"🗑️ {remove('test-agent')}")
