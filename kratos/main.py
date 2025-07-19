from agno.agent import Agent
from agno.models.lmstudio import LMStudio
from agno.tools.yfinance import YFinanceTools
from kratos.sandbox import bootstrap, invoke_agent, cleanup_agent
import cloudpickle
from typing import Optional, List
import time


def submit(agent: Agent, name: str, dependencies: Optional[List[str]] = None, recreate: bool = False) -> str:
    """Deploy an agent."""
    bootstrap(name, cloudpickle.dumps(agent), dependencies, recreate)
    return name


def invoke(name: str, task: str, print_stream: bool = True) -> None:
    """
    Run a task on an agent and handle printing internally.

    Be careful and disable print_stream if you are using a ThreadPoolExecutor.
    Otherwise, the output will be garbled.
    """
    for response in invoke_agent(name, task):
        if print_stream:
            print(response, end='', flush=True)


def remove(name: str) -> str:
    """Remove an agent."""
    cleanup_agent(name)
    return name


if __name__ == "__main__":

    print("🚀 Kratos: Serverless Intelligence Platform")
    print("=" * 45)

    # Create and deploy a single test agent
    print("🔄 Building and submitting test agent...")

    finance_agent = Agent(
        model=LMStudio(
            id="qwen/qwen3-4b",
            base_url="http://host.docker.internal:1234/v1",
        ),
        name="KratosFinance",
        tools=[YFinanceTools(stock_price=True, analyst_recommendations=True, company_info=True)],
        instructions="You are Kratos Finance Agent, specialized in stock market analysis and financial data. Use YFinance to get current stock prices, analyst recommendations, and company information. When users ask about stocks, always provide current prices and relevant financial metrics. Be precise with numbers and explain what the data means for investment decisions.",
    )
    print(f"🚀 {submit(finance_agent, 'agent-finance', dependencies=['yfinance'])}")

    # Test single agent execution with streaming
    print("\n" + "="*50)
    print("🧪 Testing Agent Execution")
    print("="*50)

    task = "Hello, please introduce yourself and tell me what you can do."
    print(f"⚡ Task: {task}")

    # Measure execution time
    start_time = time.time()

    # Run single agent invocation with streaming output
    print(f"\n🚀 Starting agent invocation at {time.strftime('%H:%M:%S')}")
    print("📡 Streaming output:\n")
    
    invoke('agent-finance', task, print_stream=True)

    end_time = time.time()
    execution_time = end_time - start_time

    print(f"\n\n⏱️  Execution time: {execution_time:.2f} seconds")

    # Cleanup the agent
    print("\n" + "="*50)
    print("💰 Cleaning up agent...")
    print(f"🗑️ {remove('agent-finance')}")
