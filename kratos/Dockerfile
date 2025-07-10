FROM ollama/ollama

# Install system dependencies (only curl needed for uv installation)
RUN apt update && apt upgrade -y && apt install -y curl

# Install uv (which will manage Python for us)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Create working directory
RUN mkdir -p /workdir
WORKDIR /workdir

# Initialize uv project and install common dependencies
# uv will automatically install the appropriate Python version
RUN uv init
RUN uv add ollama agno cloudpickle

# Set the default command to serve ollama
CMD ["serve"]
