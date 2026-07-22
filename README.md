# FridayOS

An ambient operating system intelligence powered by LiveKit, Google Gemini, and RAG-based memory.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Expo Frontend (Mobile/Web)            │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Dashboard    │  │ VoiceButton  │  │ ErrorBoundary │  │
│  │ (HUD/Status) │  │ (LiveKit     │  │ (Retry Screen)│  │
│  │              │  │  Room UI)    │  │               │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────────┘  │
│         │                 │                              │
│         └─────────────────┴── LiveKit Room ──────────────┤
│                           │                              │
└───────────────────────────┼──────────────────────────────┘
                            │ WebRTC
┌───────────────────────────┼──────────────────────────────┐
│              LiveKit Agent Server (Backend)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Friday   │  │ Tools    │  │ RAG      │  │ Ambient │ │
│  │ Agent    │  │ (25+     │  │ (ChromaDB│  │ Context │ │
│  │ (Gemini) │  │  tools)  │  │  Vector) │  │ Tracker │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────┐  ┌──────────┐                              │
│  │Automation│  │ Memory   │                              │
│  │ Manager  │  │(Postgres)│                              │
│  └──────────┘  └──────────┘                              │
└──────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Node.js** >= 18 (for Expo frontend)
- **Python** >= 3.10 (for backend)
- **LiveKit Cloud** account (free tier at https://cloud.livekit.io/)
- **Google AI** API key (https://ai.google.dev/)
- **Groq** API key (optional, for automation worker - https://console.groq.com/)

## Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

| Variable               | Required | Description                                          |
| ---------------------- | -------- | ---------------------------------------------------- |
| `LIVEKIT_URL`          | Yes      | LiveKit Cloud WebSocket URL (wss://\*.livekit.cloud) |
| `LIVEKIT_API_KEY`      | Yes      | LiveKit API key                                      |
| `LIVEKIT_API_SECRET`   | Yes      | LiveKit API secret                                   |
| `GOOGLE_API_KEY`       | Yes      | Google Gemini API key                                |
| `GROQ_API_KEY`         | No       | Groq API key (for automation worker)                 |
| `GMAIL_USER`           | No       | Gmail address for email tool                         |
| `GMAIL_APP_PASSWORD`   | No       | Gmail app password                                   |
| `HOME_ASSISTANT_URL`   | No       | Home Assistant instance URL                          |
| `HOME_ASSISTANT_TOKEN` | No       | Home Assistant long-lived token                      |
| `POSTGRES_*`           | No       | PostgreSQL connection for memory persistence         |

For the frontend, create a `FridayOS_Frontend/.env` file with:

```
EXPO_PUBLIC_LIVEKIT_URL=wss://your-project.livekit.cloud
EXPO_PUBLIC_LIVEKIT_TOKEN=your-livekit-token
```

> **Security**: Never commit `.env` files. They are already in `.gitignore`.

## Getting Started

### Backend

```bash
# Navigate to backend
cd Friday_OS/Backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run in console mode (text-only, no audio)
python main.py console

# Run in voice mode (requires LiveKit Cloud)
python main.py
```

### Frontend

```bash
# Navigate to frontend
cd FridayOS_Frontend

# Install dependencies
npm install

# Start Expo dev server
npx expo start

# Open in web browser
npm run web

# Open on Android emulator
npm run android

# Open on iOS simulator
npm run ios
```

## Usage Modes

### Console Mode

Run `python main.py console` for a text-only interface. Friday responds via text in the terminal. No audio or microphone required.

### Voice Mode

Run `python main.py` (without `console` argument) for full voice interaction. Requires:

- LiveKit Cloud account with a room configured
- Microphone access on the frontend device
- The frontend Expo app connected to the same LiveKit room

## Tool Architecture

FridayOS uses **direct `@function_tool` registrations** as its primary tool architecture. All tools are defined in `Friday_OS/Backend/tools/` using LiveKit's `@function_tool` decorator and registered in the `TOOLS` list in `main.py`.

**Available tool categories:**

- **General**: Weather, web search, email, automation worker
- **File Operations**: Create, read, delete, move, find files
- **Application Control**: Open, close, list running apps
- **Browser**: Open websites, search, read web content
- **Home Assistant**: Control smart home devices
- **Memory**: Recall past conversations
- **RAG**: Learn from documents, query knowledge base

## RAG (Retrieval Augmented Generation)

FridayOS can ingest local documents into a ChromaDB vector store for semantic recall.

```bash
# Ingest a document (via Friday's tool interface)
"Learn from my project documentation at C:\path\to\doc.md"

# Query the knowledge base
"What did I learn from my project docs?"
```

**Chunking strategies:**

- **Code files** (`.py`, `.js`, `.ts`, etc.): Line-based chunking (50 lines, 10 line overlap) to preserve syntax
- **Narrative text** (`.md`, `.txt`, `.pdf`): Sentence-boundary chunking (800 words, ~100 word overlap)
- **Dense technical docs**: Smaller word-based chunks (400 words, 50 word overlap)

## Project Structure

```
Live_Kit_Jarvis/
├── Friday_OS/
│   └── Backend/
│       ├── main.py              # Main entrypoint (ACTIVE)
│       ├── agent.py             # DEPRECATED - see main.py
│       ├── core/
│       │   ├── friday_rag.py    # RAG engine with ChromaDB
│       │   ├── automation.py    # Automation manager
│       │   └── tracker.py       # Ambient context tracker
│       ├── tools/
│       │   ├── tools.py         # General tools (weather, email, search)
│       │   ├── tools_apps.py    # Application control tools
│       │   ├── tools_browser.py # Browser tools
│       │   ├── tools_files.py   # File operation tools
│       │   ├── tools_memory.py  # Memory recall tools
│       │   └── home_assistant_tools.py
│       ├── memory.py            # Memory initialization
│       └── prompts.py           # System prompts
├── FridayOS_Frontend/
│   ├── App.tsx                  # Root component with LiveKit + ErrorBoundary
│   ├── app/
│   │   ├── _layout.tsx          # App layout
│   │   └── index.tsx            # Dashboard/HUD screen
│   ├── components/
│   │   ├── VoiceButton.tsx      # LiveKit room connection UI
│   │   └── ErrorBoundary.tsx    # Error boundary with retry
│   └── hooks/
│       ├── useLiveKit.tsx       # LiveKit room context + provider
│       └── useFridayOS.ts       # WebSocket bridge (legacy)
├── tests/
│   ├── test_agent.py            # Agent instantiation tests
│   ├── test_rag.py              # RAG chunking + ingest/query tests
│   └── test_tools.py            # SMTP email tool tests
├── .env.example                 # Environment variable template
├── .gitignore
└── README.md
```

## Troubleshooting

| Issue                     | Solution                                                                  |
| ------------------------- | ------------------------------------------------------------------------- |
| `GROQ_API_KEY not found`  | Set `GROQ_API_KEY` in `.env` (optional, for automation worker)            |
| LiveKit connection fails  | Verify `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` are correct |
| Expo shows white screen   | Check the ErrorBoundary - it will show a retry screen with details        |
| SMTP email fails          | Use a Gmail App Password, not your regular password                       |
| RAG query returns nothing | Ensure documents were ingested successfully first                         |
| `agent.py` confusion      | `agent.py` is deprecated. Use `main.py` as the entrypoint                 |

## Running Tests

```bash
# From the project root
cd Friday_OS/Backend
python -m pytest ../../tests/ -v
```

## License

See `FridayOS_Frontend/LICENSE`.
