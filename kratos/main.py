from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from agno.tools.youtube import YouTubeTools
from sandbox import bootstrap, invoke_agent, cleanup_agent
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


def create_web_search_agent(model: str) -> Agent:
    """Create a Kratos agent specialized for web search."""
    return Agent(
        model=Ollama(id=model),
        name="KratosWebSearch",
        tools=[DuckDuckGoTools()],
        instructions="You are Kratos Web Search Agent, specialized in finding current information from the web. Use DuckDuckGo to search for the latest news, facts, and information. Always provide up-to-date and accurate information from reliable sources. Be concise and focus on delivering the most relevant search results.",
        show_tool_calls=False,
    )


def create_finance_agent(model: str) -> Agent:
    """Create a Kratos agent specialized for financial data."""
    return Agent(
        model=Ollama(id=model),
        name="KratosFinance",
        tools=[YFinanceTools(stock_price=True, analyst_recommendations=True, company_info=True)],
        instructions="You are Kratos Finance Agent, specialized in stock market analysis and financial data. Use YFinance to get current stock prices, analyst recommendations, and company information. When users ask about stocks, always provide current prices and relevant financial metrics. Be precise with numbers and explain what the data means for investment decisions.",
        show_tool_calls=False,
    )


def create_youtube_agent(model: str) -> Agent:
    """Create a Kratos agent specialized for YouTube analysis."""
    return Agent(
        model=Ollama(id=model),
        name="KratosYouTube",
        tools=[YouTubeTools()],
        instructions="You are Kratos YouTube Agent, specialized in analyzing YouTube videos and transcripts. Use YouTube tools to extract video information, transcripts, and analyze content. When users mention YouTube videos, provide detailed analysis of the content, key points, and insights from the transcript. Be thorough in your analysis and highlight important information.",
        show_tool_calls=False,
    )


if __name__ == "__main__":
    import time

    print("🚀 Kratos: Serverless Intelligence Platform")
    print("=" * 45)

    # # Create and deploy a single test agent
    # print("🔄 Building and submitting test agent...")

    # test_agent = create_web_search_agent("qwen3:1.7b")
    # print(f"🚀 {submit(test_agent, 'test-agent')}")

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
    # print("\n" + "="*50)
    # print("💰 Cleaning up agent...")
    # print(f"🗑️ {remove('test-agent')}")
