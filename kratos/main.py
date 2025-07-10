from typing import Iterator
from agno.agent import Agent, RunResponseEvent
from agno.models.openai import OpenAIChat
from agno.utils.pprint import pprint_run_response

agent = Agent(model=OpenAIChat(id="gpt-4-mini"))

# Run agent and return the response as a stream
response_stream: Iterator[RunResponseEvent] = agent.run(
    "Tell me a 5 second short story about a lion",
    stream=True
)

# Print the response stream in markdown format
pprint_run_response(response_stream, markdown=True)


## Tool calls - any function, in this case get_top_hackernews_stories, can be converted into a tool:
# agent = Agent(tools=[get_top_hackernews_stories], show_tool_calls=True, markdown=True)
# agent.print_response("Summarize the top 5 stories on hackernews?", stream=True)