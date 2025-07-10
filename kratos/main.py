from agno.agent import Agent
from typing import Optional, List
from microvm import bootstrap, run_agent, cleanup_agent
import cloudpickle


def submit(agent: Agent, name: str, dependencies: Optional[List[str]] = None) -> str:
    return ""


def run(name: str, instruction: str) -> str:
    return ""


if __name__ == "__main__":
    agent_name = "test-agent"
    
    # Bootstrap once (like Lambda cold start)
    print("Bootstrapping agent...")
    bootstrap(agent_name, cloudpickle.dumps("coco"))
    
    # Run multiple times (like Lambda warm invocations)
    print("\nRunning agent multiple times...")
    for i in range(3):
        print(f"\n--- Invocation {i+1} ---")
        result = run_agent(agent_name, f"invocation-{i+1}")
    
    # Clean up when done
    print("\nCleaning up...")
    cleanup_agent(agent_name)
