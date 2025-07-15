# kratos

Kratos is a serverless intelligence platform for running ephemeral AI agents in isolated microVMs.

🎯 Core Vision:
•  Serverless compute platform for ephemeral agents
•  Micro-task execution: search, parsing, editing, content generation
•  Per-second billing model with strict resource limits
•  Energy-efficient compute optimized for ARM/Apple Silicon
•  Massively parallel execution without long-running processes

🏗️ Architecture:
•  Docker containers (temporary, will migrate to Apple Containers)
•  Lightweight, fast-launching environments similar to Firecracker
•  Ephemeral agents that spawn on demand and shut down immediately
•  Model-specific pulling for efficiency

🚀 Core API Functions:
1. submit() - Deploy serverless agent for micro-task execution
2. invoke() - Execute micro-tasks with burst efficiency  

🔧 Technical Features:
•  Model extraction ensures only required models are pulled
•  Resource reclamation for efficient billing
•  Burst execution optimized for short-lived tasks

The system now embodies Kratos as "intelligence as a utility" - making AI accessible through efficient, ephemeral compute that scales like serverless functions but optimized for local, energy-efficient execution.
