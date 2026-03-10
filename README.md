# assistant-ui + A2A Kitchen Sink

A comprehensive example showing [assistant-ui](https://github.com/assistant-ui/assistant-ui) connected to an [A2A (Agent-to-Agent)](https://google.github.io/A2A/) server, demonstrating all major protocol features.

```
Frontend (Next.js)  -->  Bridge Backend (FastAPI)  -->  A2A Server
     :3000                    :8000                       :9999
```

## Features

| Skill | Command | A2A Features |
|-------|---------|-------------|
| **Chat** | _(any message)_ | Streaming text via TaskStatusUpdateEvent |
| **Artifacts** | `/artifacts <prompt>` | Text, data, and file artifacts |
| **Multi-step** | `/multistep [topic]` | `input-required` task state |
| **Failure** | `/fail` | `failed` task state, error handling |
| **Slow task** | `/slow` | Long-running task, cancellation |

The frontend shows a live tool UI with:
- Agent Card display (name, skills, capabilities, version)
- Task state badges with live transitions
- Streaming text updates
- Artifact rendering (code, structured data, files)
- Error states

## Prerequisites

- Node.js >= 18
- Python >= 3.10
- An OpenAI API key

## Setup

### 1. A2A Server (port 9999)

```bash
cd a2a-server
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

python -m venv .venv
source .venv/bin/activate
pip install -e .

python main.py
```

### 2. Bridge Backend (port 8000)

```bash
cd a2a-backend
cp .env.example .env

python -m venv .venv
source .venv/bin/activate
pip install -e .

python main.py
```

### 3. Frontend (port 3000)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. You can change the A2A server URL in the input field at the top. Use the suggestion buttons to try each skill.
