import cloudpickle
import sys
import argparse
import lmstudio as lms


# Parse command line arguments
parser = argparse.ArgumentParser(description='Execute Kratos agent')
parser.add_argument('--model_name', required=True, help='Model name for the agent')
parser.add_argument('--container_name', required=True, help='Container name for this execution')
parser.add_argument('--instructions', required=True, help='Instructions for the agent to execute')

args = parser.parse_args()

# Load the agent from the pickle file
with open('/workdir/agent.pkl', 'rb') as f:
    agent = cloudpickle.load(f)

# Run the agent with streaming enabled
try:
    response = agent.run(args.instructions, stream=True)
    
    # Handle streaming response properly
    if hasattr(response, '__iter__') and not isinstance(response, str):
        # Streaming response - print chunks as they come
        for chunk in response:
            if hasattr(chunk, 'content') and chunk.content:
                print(chunk.content, end='', flush=True)
            elif hasattr(chunk, 'text') and chunk.text:
                print(chunk.text, end='', flush=True)
            elif isinstance(chunk, str):
                print(chunk, end='', flush=True)
            else:
                print(str(chunk), end='', flush=True)
    else:
        # Non-streaming response
        if hasattr(response, 'content'):
            print(response.content, end='', flush=True)  # pyright: ignore
        else:
            print(response, end='', flush=True)
except Exception as e:
    print(f"Error running agent (model: {args.model_name}, container: {args.container_name}): {e}", file=sys.stderr)
    sys.exit(1)

