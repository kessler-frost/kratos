from agno.agent import Agent
from typing import Optional, List
from microvm import bootstrap, run_agent
import cloudpickle


def submit(agent: Agent, name: str, dependencies: Optional[List[str]] = None) -> str:
    return ""


def run(name: str, instruction: str) -> str:
    return ""


if __name__ == "__main__":
    # bootstrap("test-agent", cloudpickle.dumps("coco"))
    run_agent("test-agent", "samplabiley")