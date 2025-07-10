from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from agno.tools.youtube import YouTubeTools
from kratos.sandbox import bootstrap, invoke_agent, cleanup_agent
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


def create_web_search_agent() -> Agent:
    """Create a Kratos agent specialized for web search."""
    return Agent(
        model=Ollama(id="qwen3:1.7b"),
        name="KratosWebSearch",
        tools=[DuckDuckGoTools()],
        instructions="You are Kratos Web Search Agent, specialized in finding current information from the web. Use DuckDuckGo to search for the latest news, facts, and information. Always provide up-to-date and accurate information from reliable sources. Be concise and focus on delivering the most relevant search results.",
        show_tool_calls=False,
    )


def create_finance_agent() -> Agent:
    """Create a Kratos agent specialized for financial data."""
    return Agent(
        model=Ollama(id="qwen3:1.7b"),
        name="KratosFinance",
        tools=[YFinanceTools(stock_price=True, analyst_recommendations=True, company_info=True)],
        instructions="You are Kratos Finance Agent, specialized in stock market analysis and financial data. Use YFinance to get current stock prices, analyst recommendations, and company information. When users ask about stocks, always provide current prices and relevant financial metrics. Be precise with numbers and explain what the data means for investment decisions.",
        show_tool_calls=False,
    )


def create_youtube_agent() -> Agent:
    """Create a Kratos agent specialized for YouTube analysis."""
    return Agent(
        model=Ollama(id="qwen3:1.7b"),
        name="KratosYouTube",
        tools=[YouTubeTools()],
        instructions="You are Kratos YouTube Agent, specialized in analyzing YouTube videos and transcripts. Use YouTube tools to extract video information, transcripts, and analyze content. When users mention YouTube videos, provide detailed analysis of the content, key points, and insights from the transcript. Be thorough in your analysis and highlight important information.",
        show_tool_calls=False,
    )


if __name__ == "__main__":
    print("🚀 Kratos: Serverless Intelligence Platform")
    print("=" * 45)

    # Deploy three specialized agents
    print("🔄 Building and submitting agents...")

    web_agent = create_web_search_agent()
    print(f"🚀 {submit(web_agent, 'kratos-1')}")

    finance_agent = create_finance_agent()
    print(f"🚀 {submit(finance_agent, 'kratos-2')}")

    youtube_agent = create_youtube_agent()
    print(f"🚀 {submit(youtube_agent, 'kratos-3')}")

    # Test each agent with specialized tasks
    print("\n" + "="*50)
    print("🧪 Testing Web Search Agent (kratos-1)")
    print("="*50)
    web_task = "Search for the latest news about artificial intelligence breakthroughs in 2024"
    print(f"⚡ Task: {web_task}")
    print("💬 Response:")
    for response_chunk in invoke('kratos-1', web_task):
        print(response_chunk, end='', flush=True)
    print()

    print("\n" + "="*50)
    print("🧪 Testing Finance Agent (kratos-2)")
    print("="*50)
    finance_task = "Get the current stock price of Tesla (TSLA) and analyst recommendations"
    print(f"⚡ Task: {finance_task}")
    print("💬 Response:")
    for response_chunk in invoke('kratos-2', finance_task):
        print(response_chunk, end='', flush=True)
    print()

    print("\n" + "="*50)
    print("🧪 Testing YouTube Agent (kratos-3)")
    print("="*50)
    youtube_task = "Analyze the YouTube video with URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"⚡ Task: {youtube_task}")
    print("💬 Response:")
    for response_chunk in invoke('kratos-3', youtube_task):
        print(response_chunk, end='', flush=True)
    print()

    # Cleanup all agents
    print("\n" + "="*50)
    print("💰 Cleaning up agents...")
    print(f"🗑️ {remove('kratos-1')}")
    print(f"🗑️ {remove('kratos-2')}")
    print(f"🗑️ {remove('kratos-3')}")
