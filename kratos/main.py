from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from agno.tools.youtube import YouTubeTools
from microvm import bootstrap, invoke_agent, cleanup_agent
import cloudpickle
from typing import Iterator


def submit(agent: Agent, name: str) -> str:
    """Deploy an agent."""
    try:
        dependencies = ["ddgs", "duckduckgo-search", "yfinance", "youtube-transcript-api"]
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


def create_agent() -> Agent:
    """Create a Kratos agent with tools."""
    return Agent(
        model=Ollama(id="qwen3:1.7b"),
        name="KratosAgent",
        tools=[
            DuckDuckGoTools(),  # Web search tool
            YFinanceTools(stock_price=True, analyst_recommendations=True, company_info=True),  # Finance tool
            YouTubeTools()  # YouTube transcript and video information tool
        ],
        instructions="You are Kratos, an intelligent assistant with access to powerful tools. Use DuckDuckGo for web searches, YFinance for stock prices and financial data, and YouTube tools for video transcript analysis. When users ask about stocks, always get current prices. When they mention YouTube videos, extract and analyze transcripts. For general information, search the web. Be concise, accurate, and always leverage your tools to provide the most current information.",
        show_tool_calls=True,  # Show which tools are being used
        markdown=True          # Format responses in markdown
    )


if __name__ == "__main__":
    print("🚀 Kratos: Serverless Intelligence Platform")
    print("=" * 45)
    
    # Deploy
    print("🔄 Building and submitting agent...")
    agent = create_agent()
    print(f"🚀 {submit(agent, 'kratos')}")
    
    # Tasks
    task = "Search the web for the current stock price of Apple (AAPL) and tell me if it's a good investment"
    print(f"\n⚡ Task: {task}")
    print("💬 Response:")
    
    # Stream the response as it comes
    for response_chunk in invoke('kratos', task):
        print(response_chunk, end='', flush=True)
    
    print()  # New line after streaming is complete
    
    # Cleanup
    print(f"\n💰 {remove('kratos')}")
