import cloudpickle
import argparse
import lmstudio as lms

lms.configure_default_client("host.docker.internal:1234")

# Parse command line arguments
parser = argparse.ArgumentParser(description='Execute Kratos agent')
parser.add_argument('--model_name', required=True, help='Model name for the agent')
parser.add_argument('--instructions', required=True, help='Instructions for the agent to execute')

args = parser.parse_args()
# Load the agent from the pickle file
with open('/workdir/agent.pkl', 'rb') as f:
    agent = cloudpickle.load(f)

# Tell LMStudio to load the model
client = lms.get_default_client()
model = client.llm.load_new_instance(model_key=args.model_name)

# Run the agent with streaming enabled
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

# Unload the model
model.unload()

