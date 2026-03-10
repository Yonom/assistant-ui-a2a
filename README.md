# assistant-ui + A2A Example

An example showing [assistant-ui](https://github.com/assistant-ui/assistant-ui) connected to an [A2A (Agent-to-Agent)](https://google.github.io/A2A/) server via a bridge backend.

```
Frontend (Next.js)  -->  Bridge Backend (FastAPI)  -->  A2A Server
     :3000                    :8000                       :9999
```

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

Open http://localhost:3000. You can change the A2A server URL in the input field at the top.
