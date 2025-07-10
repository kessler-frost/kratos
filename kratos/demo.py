#!/usr/bin/env python3
"""
Kratos Demo: Serverless compute platform for ephemeral agents

Demonstrates lightweight, short-lived agents handling micro-tasks like search,
parsing, editing, and content generation with per-second billing efficiency.

Core operations:
1. submit() - Deploy serverless agent for micro-task execution
2. invoke() - Execute micro-tasks with burst efficiency
3. remove() - Teardown and reclaim resources
"""

from main import submit, invoke, remove, create_simple_agent


def demo_kratos_micro_tasks():
    """Demonstrate Kratos serverless micro-task execution."""
    
    print("🚀 Kratos Demo - Serverless Micro-Task Platform")
    print("=" * 50)
    
    # Step 1: Deploy serverless agent
    print("📦 Deploying serverless agent for micro-tasks...")
    agent = create_simple_agent()
    agent_name = "micro-task-demo"
    
    deployment_result = submit(agent, agent_name)
    print(f"✅ {deployment_result}")
    
    # Step 2: Execute burst of micro-tasks (typical Kratos workload)
    print(f"\n⚡ Executing burst micro-tasks on '{agent_name}'...")
    
    micro_tasks = [
        "Parse email 'john.doe@company.com' and extract company name",
        "Generate 5 keywords for a fitness tracking app",
        "Summarize: 'Q3 revenue grew 23% driven by mobile adoption'",
        "Convert text 'URGENT_PROJECT_DEADLINE' to title case",
        "Extract the action item from: 'Please review the proposal by Friday'"
    ]
    
    for i, task in enumerate(micro_tasks, 1):
        print(f"\n📊 Micro-task {i}: {task}")
        response = invoke(agent_name, task)
        print(f"🚀 Result: {response}")
    
    # Step 3: Teardown and reclaim resources
    print(f"\n💰 Tearing down agent '{agent_name}' and reclaiming resources...")
    removal_result = remove(agent_name)
    print(f"✅ {removal_result}")
    
    print("\n🎉 Kratos micro-task demo completed!")


def demo_multiple_agents():
    """Demonstrate deploying and managing multiple agents."""
    
    print("\n" + "=" * 50)
    print("🔀 Multiple Agents Demo")
    print("=" * 50)
    
    # Deploy multiple agents
    agents = []
    for i in range(2):
        agent_name = f"agent-{i+1}"
        print(f"\n📦 Creating and deploying {agent_name}...")
        
        agent = create_simple_agent()
        deployment_result = submit(agent, agent_name)
        agents.append(agent_name)
        print(f"✅ {deployment_result}")
    
    # Invoke all agents
    instruction = "Tell me a fun fact about space."
    print(f"\n⚡ Invoking all agents with: '{instruction}'")
    
    for agent_name in agents:
        print(f"\n🤖 {agent_name}:")
        response = invoke(agent_name, instruction)
        print(f"💬 {response}")
    
    # Clean up all agents
    print(f"\n🧹 Cleaning up all agents...")
    for agent_name in agents:
        removal_result = remove(agent_name)
        print(f"✅ {removal_result}")


if __name__ == "__main__":
    try:
        demo_kratos_micro_tasks()
        demo_multiple_agents()
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
