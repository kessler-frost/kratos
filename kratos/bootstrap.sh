#!/bin/bash

set -e

echo "Starting bootstrap script"

# create a directory with a random 4 character name
random_dir_name=$(openssl rand -hex 2)
mkdir -p runs/$random_dir_name
cd runs/$random_dir_name
echo "Created directory: $random_dir_name"

apt update && apt upgrade -y && apt install -y curl

curl -LsSf https://astral.sh/uv/install.sh | sh

uv init
uv add ollama agno cloudpickle
