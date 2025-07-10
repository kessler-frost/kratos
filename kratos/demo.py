#!/usr/bin/env python3
"""
Demo script showing Lambda-style ephemeral agent deployment and invocation.

This demonstrates the three main operations:
1. submit() - Deploy an ephemeral agent (like Lambda deployment)
2. invoke() - Execute the ephemeral agent with instructions (like Lambda invocation)
3. remove() - Destroy the ephemeral agent
"""

from main import submit, invoke, remove, create_simple_agent


def demo_lambda_style_agent():
    """Demonstrate Lambda-style ephemeral agent operations."""
    
    print("🚀 Kratos Ephemeral Agent Demo - Lambda-style Deployment")
    print("=" * 55)
    
    # Step 1: Create an ephemeral agent
    print("📦 Creating ephemeral agent...")
    agent = create_simple_agent()
    agent_name = "ephemeral-demo-agent"
    
    # Step 2: Submit (deploy) the ephemeral agent
    print(f"\n🔄 Deploying ephemeral agent '{agent_name}'...")
    deployment_result = submit(agent, agent_name)
    print(f"✅ {deployment_result}")
    
    # Step 3: Invoke the ephemeral agent multiple times
    print(f"\n⚡ Invoking ephemeral agent '{agent_name}' with different instructions...")
    
    test_cases = [
        "Explain quantum computing in one sentence.",
        "Write a haiku about programming.",
        "What's the difference between Docker and virtual machines?"
    ]
    
    for i, instruction in enumerate(test_cases, 1):
        print(f"\n🎯 Test {i}: {instruction}")
        response = invoke(agent_name, instruction)
        print(f"💬 Agent: {response}")
    
    # Step 4: Clean up
    print(f"\n🧹 Removing agent '{agent_name}'...")
    removal_result = remove(agent_name)
    print(f"✅ {removal_result}")
    
    print("\n🎉 Demo completed successfully!")


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
        demo_lambda_style_agent()
        demo_multiple_agents()
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
