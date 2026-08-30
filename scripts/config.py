"""Hand-maintained knobs for the profile generator.

Everything in this file is editorial: which repos to hide, how to name the
technical categories, and the short "why it's interesting" notes that a script
can't infer honestly. Facts (stars, languages, dates, dependencies, activity)
are always fetched live -- never written here.
"""

USER = "Dinesh-Sharma2004"
DISPLAY_NAME = "Dinesh Sharma"

# Identity line. Derived from the repos, not aspiration: the dominant shape
# across the public repos is a Python/FastAPI service with a retrieval or LLM
# layer, a React front end, and a real deployment target.
TAGLINE = "Backend & AI systems engineer"
SUBLINE = "I build retrieval and LLM-backed services in Python, then containerise and ship them."

LINKS = [
    ("GitHub", "https://github.com/Dinesh-Sharma2004"),
    ("Portfolio", "https://personal-portfolio-puce-chi-17.vercel.app"),
]

# ---------------------------------------------------------------------------
# Repos deliberately kept out of every generated section.
#
# SI_CL_SDEO and VA_ASTE are paper-reproduction / academic work and are excluded
# by request. Search-Sentimentizer is excluded by request. Dinesh-Sharma2004 is
# this repo itself. Forks are dropped automatically by the fetcher, so they
# don't need listing.
# ---------------------------------------------------------------------------
EXCLUDE_REPOS = {
    "SI_CL_SDEO",
    "VA_ASTE",
    "Search-Sentimentizer",
    "Dinesh-Sharma2004",
}

# ---------------------------------------------------------------------------
# Featured projects, ordered by engineering depth rather than stars.
#
# `what` must describe only what the repo demonstrably does.
# `why` is the technical reason it is worth a reader's time.
# `tech` is a display override; if omitted the fetcher's detected stack is used.
# ---------------------------------------------------------------------------
FEATURED = [
    {
        "repo": "Medical_chatbot",
        "title": "Medical Chatbot",
        "what": "Full-stack RAG service: upload PDFs, build a FAISS index off the "
                "request path, then ask questions against them with streamed answers.",
        "tech": ["Python", "FastAPI", "LangChain", "FAISS", "Redis / RQ",
                 "PostgreSQL", "React", "Vite", "Docker", "Kubernetes", "Prometheus"],
        "why": "Ingestion is a separate Redis/RQ worker that rebuilds the vector index "
               "outside the API request path, so uploads never block queries. Ships with "
               "Kubernetes manifests (HPA, PDB, ingress, RWX PVCs shared between API and "
               "worker), a Prometheus/Grafana stack, and a GitLab pipeline that builds "
               "images and deploys to EKS.",
    },
    {
        "repo": "KYC_Face_Verifier",
        "title": "KYC Verification Platform",
        "what": "Document-verification platform: OCR extraction, face matching and "
                "job tracking behind an API gateway with Celery workers.",
        "tech": ["Python", "FastAPI", "Celery", "Redis", "PostgreSQL", "SQLModel",
                 "Streamlit", "React", "TypeScript", "Docker", "Fly.io"],
        "why": "The interesting part is the design work, not just the code: a normalised "
               "ERD with soft deletes and document versioning, a versioned async event "
               "envelope carrying trace and idempotency keys across services, and a "
               "written security plan covering upload sniffing, tenant-scoped RBAC and "
               "retention. Includes an honest architecture audit of what the repo does "
               "and does not yet have.",
    },
    {
        "repo": "FactLens",
        "title": "ET FactLens",
        "what": "Claim-verification workspace that streams verdicts, summarises news "
                "URLs, transcribes audio and scores image relevance.",
        "tech": ["Python", "FastAPI", "SSE", "Redis", "Groq", "Whisper", "CLIP / ViT",
                 "SerpAPI", "React", "Tailwind", "Docker Compose"],
        "why": "Cache-first corrective RAG: repeat checks are answered from cache before "
               "any retrieval happens, and evidence carries stable REF_00x IDs so a verdict "
               "can be traced to sources. Every external dependency has a fallback -- Redis "
               "degrades to in-memory, the hosted ViT endpoint degrades to local CLIP, a "
               "missing Groq key degrades to mock responses.",
    },
    {
        "repo": "TripCaspian",
        "title": "BizPulse",
        "what": "Agent that turns conversational promises (\"I'll pay by Friday\") into "
                "tracked obligations and follows up when they come due.",
        "tech": ["Python", "Caspian SDK", "Gemini", "APScheduler", "SQLite",
                 "pytest", "Docker", "Vercel"],
        "why": "A deterministic signal gate scores each message for action verbs, money "
               "terms and obligation phrases, and drops anything under threshold for zero "
               "tokens -- the LLM only runs when language understanding is actually needed, "
               "with a rule-based extractor as offline fallback. Commitments move through a "
               "nine-state machine, and an APScheduler job store plus an independent "
               "overdue poller means a missed alert is caught twice.",
    },
    {
        "repo": "HLE-Benchmark-Test",
        "title": "LLM Evaluation Harness",
        "what": "Config-driven harness for running the same benchmark across several "
                "models and comparing the results reproducibly.",
        "tech": ["Python", "asyncio", "Pydantic", "OpenRouter", "matplotlib"],
        "why": "Built for long runs that fail halfway: an async producer/consumer pool "
               "adapts its rate from response headers, prompts are cached by hash so a "
               "resumed run doesn't re-pay for completed work, and checkpoints let a run "
               "continue into a fresh timestamped folder. Scored comparisons use McNemar "
               "and Wilcoxon with bootstrap confidence intervals instead of raw accuracy "
               "deltas.",
    },
    {
        "repo": "Trading-bot",
        "title": "Binance Futures Trading Bot",
        "what": "USDT-M futures client with a live dashboard: market, limit, "
                "stop-limit, OCO, TWAP and grid order execution.",
        "tech": ["Python", "Flask", "WebSockets", "python-binance",
                 "React", "Tailwind", "Vite"],
        "why": "The order layer is split by strategy rather than lumped into one handler, "
               "so OCO cancellation, TWAP slicing and grid laddering each stay testable in "
               "isolation. Runs against testnet or in simulation with no credentials, and "
               "the React side renders candlesticks and a live order book off a WebSocket "
               "price feed.",
    },
]

# ---------------------------------------------------------------------------
# System map. Each leaf must be backed by files in the public repos; `evidence`
# lists the repos it comes from so the claim stays checkable.
# ---------------------------------------------------------------------------
SYSTEM_MAP = {
    "root": "WHAT I BUILD",
    "sink": "DEPLOYED APPLICATIONS",
    "branches": [
        {
            "name": "AI / ML SYSTEMS",
            "leaves": ["RAG pipelines", "LLM agents", "Eval harnesses"],
            "evidence": ["Medical_chatbot", "FactLens", "TripCaspian",
                         "HLE-Benchmark-Test", "tweeter-assistant"],
        },
        {
            "name": "BACKEND SERVICES",
            "leaves": ["FastAPI APIs", "Queues & workers", "State machines"],
            "evidence": ["Medical_chatbot", "KYC_Face_Verifier",
                         "MagicPin-challenge", "Affordmed_assignment"],
        },
        {
            "name": "DATA & RETRIEVAL",
            "leaves": ["Vector search", "Scrapers & ETL", "Cache layers"],
            "evidence": ["Medical_chatbot", "FactLens",
                         "Data-Scrapping-Assignment", "ET_Hack"],
        },
        {
            "name": "INFRA & DELIVERY",
            "leaves": ["Docker & K8s", "CI/CD", "Metrics & alerts"],
            "evidence": ["Medical_chatbot", "KYC_Face_Verifier", "FactLens", "ET_Hack"],
        },
        {
            "name": "INTERFACES",
            "leaves": ["React dashboards", "Streaming UIs", "Bots & CLIs"],
            "evidence": ["Trading-bot", "Apna-Fit", "Medical_chatbot",
                         "TripCaspian", "Dinesh-Sharma"],
        },
    ],
}

# Four-card "what kind of engineer is this" summary.
WHAT_I_BUILD = [
    ("AI / LLM SERVICES", "retrieval, streaming, agents"),
    ("BACKEND SYSTEMS", "APIs, workers, state machines"),
    ("DATA & RETRIEVAL", "vector search, scraping, caching"),
    ("DEV TOOLING & OPS", "eval harnesses, containers, CI"),
]

# ---------------------------------------------------------------------------
# Tech detection.
#
# Ordered list of (canonical name, category, [regex patterns]). A technology is
# only reported if one of its patterns matches a real dependency manifest or a
# real path in a repo's git tree. Patterns are matched case-insensitively.
#
# Category order here is the display order in the README.
# ---------------------------------------------------------------------------
CATEGORY_ORDER = [
    "Languages",
    "AI / ML",
    "Backend",
    "Frontend",
    "Data & Storage",
    "Infrastructure",
    "Testing & Tooling",
]

# Languages come from the GitHub /languages endpoint, not from patterns.
LANGUAGE_CATEGORY = "Languages"

DETECT = [
    # ---- AI / ML -----------------------------------------------------------
    ("LangChain",        "AI / ML",           [r"^langchain"]),
    ("FAISS",            "AI / ML",           [r"^faiss", r"faiss[-_]cpu"]),
    ("Groq",             "AI / ML",           [r"^groq", r"langchain[-_]groq"]),
    ("Google Gemini",    "AI / ML",           [r"google[-_]genai", r"google[-_]generativeai",
                                               r"^google-cloud-aiplatform"]),
    ("OpenRouter",       "AI / ML",           [r"openrouter"]),
    ("Hugging Face",     "AI / ML",           [r"^transformers", r"huggingface[-_]hub",
                                               r"^fastembed", r"sentence[-_]transformers"]),
    ("PyTorch",          "AI / ML",           [r"^torch$", r"^torchvision", r"^torchaudio"]),
    ("Whisper",          "AI / ML",           [r"whisper"]),
    ("CLIP / ViT",       "AI / ML",           [r"^open[-_]?clip", r"clip[-_]model"]),
    ("scikit-learn",     "AI / ML",           [r"scikit[-_]learn", r"^sklearn"]),
    ("LightGBM",         "AI / ML",           [r"^lightgbm"]),
    ("NumPy",            "AI / ML",           [r"^numpy"]),
    ("pandas",           "AI / ML",           [r"^pandas"]),
    ("OpenCV",           "AI / ML",           [r"opencv[-_]python", r"^cv2"]),
    ("Tesseract OCR",    "AI / ML",           [r"pytesseract", r"tesseract"]),

    # ---- Backend -----------------------------------------------------------
    ("FastAPI",          "Backend",           [r"^fastapi"]),
    ("Uvicorn",          "Backend",           [r"^uvicorn"]),
    ("Pydantic",         "Backend",           [r"^pydantic"]),
    ("Flask",            "Backend",           [r"^flask"]),
    ("Express",          "Backend",           [r"^express$"]),
    ("Celery",           "Backend",           [r"^celery"]),
    ("RQ",               "Backend",           [r"^rq$", r"^rq-"]),
    ("APScheduler",      "Backend",           [r"apscheduler"]),
    ("WebSockets",       "Backend",           [r"^websockets?$", r"flask[-_]socketio",
                                               r"^socket\.io", r"python[-_]socketio"]),
    ("Streamlit",        "Backend",           [r"^streamlit"]),
    ("Gradio",           "Backend",           [r"^gradio"]),
    ("BeautifulSoup",    "Backend",           [r"beautifulsoup", r"^bs4$"]),

    # ---- Frontend ----------------------------------------------------------
    ("React",            "Frontend",          [r"^react$", r"^react-dom$"]),
    ("Vite",             "Frontend",          [r"^vite$", r"@vitejs/"]),
    ("Next.js",          "Frontend",          [r"^next$"]),
    ("Tailwind CSS",     "Frontend",          [r"^tailwindcss$"]),
    ("Framer Motion",    "Frontend",          [r"^framer-motion$"]),
    ("GSAP",             "Frontend",          [r"^gsap$"]),
    ("TanStack Query",   "Frontend",          [r"@tanstack/react-query"]),
    ("Recharts",         "Frontend",          [r"^recharts$"]),

    # ---- Data & Storage ----------------------------------------------------
    ("PostgreSQL",       "Data & Storage",    [r"^psycopg", r"^asyncpg$", r"^pg$",
                                               r"postgresql", r"^pgvector"]),
    ("Redis",            "Data & Storage",    [r"^redis$", r"^ioredis$"]),
    ("SQLAlchemy",       "Data & Storage",    [r"^sqlalchemy", r"^sqlmodel$"]),
    ("SQLite",           "Data & Storage",    [r"\.sqlite3?$", r"aiosqlite"]),
    ("Drizzle ORM",      "Data & Storage",    [r"^drizzle-orm$"]),
    ("Alembic",          "Data & Storage",    [r"^alembic$"]),

    # ---- Infrastructure ----------------------------------------------------
    ("Docker",           "Infrastructure",    [r"^dockerfile", r"/dockerfile",
                                               r"^dockerfile\."]),
    ("Docker Compose",   "Infrastructure",    [r"^docker-compose.*\.ya?ml$",
                                               r"^compose\.ya?ml$"]),
    ("Kubernetes",       "Infrastructure",    [r"^k8s/", r"kustomization\.ya?ml$"]),
    ("GitHub Actions",   "Infrastructure",    [r"^\.github/workflows/.+\.ya?ml$"]),
    ("GitLab CI",        "Infrastructure",    [r"^\.gitlab-ci\.ya?ml$"]),
    ("Prometheus",       "Infrastructure",    [r"prometheus", r"prometheus[-_]client"]),
    ("Grafana",          "Infrastructure",    [r"grafana"]),
    ("Nginx",            "Infrastructure",    [r"nginx\.conf$"]),
    ("Render",           "Infrastructure",    [r"^render\.ya?ml$"]),
    ("Vercel",           "Infrastructure",    [r"^vercel\.json$"]),
    ("Fly.io",           "Infrastructure",    [r"^fly\.toml$"]),
    ("Gunicorn",         "Infrastructure",    [r"^gunicorn$"]),

    # ---- Testing & Tooling -------------------------------------------------
    ("pytest",           "Testing & Tooling", [r"^pytest$", r"^pytest-"]),
    ("unittest",         "Testing & Tooling", [r"^tests?/test_.+\.py$",
                                               r"^testing/tests/"]),
    ("uv",               "Testing & Tooling", [r"^uv\.lock$"]),
    ("Bun",              "Testing & Tooling", [r"^bun\.lock", r"^bun\.lockb$"]),
    ("pnpm",             "Testing & Tooling", [r"^pnpm-lock\.ya?ml$",
                                               r"^pnpm-workspace\.ya?ml$"]),
    ("ESLint",           "Testing & Tooling", [r"^eslint", r"eslint\.config\.js$"]),
]

# Manifests worth downloading per repo (matched against the git tree, then
# fetched raw). Kept small so a full refresh stays cheap.
MANIFEST_NAMES = (
    "requirements.txt",
    "requirements-dev.txt",
    "package.json",
    "pyproject.toml",
)
MAX_MANIFESTS_PER_REPO = 8

# A repo counts as "active" if it was pushed to within this many days.
ACTIVE_WINDOW_DAYS = 30
# Minimum repos to show in Currently Building, even if the window is quiet.
CURRENTLY_BUILDING_COUNT = 3

# Status labels for Currently Building, chosen from real signals:
#   Active    -> pushed inside the active window
#   Improving -> mature repo (older than 120 days) touched inside 90 days
#   Exploring -> created inside 60 days, few commits
STATUS_ACTIVE = "Active"
STATUS_IMPROVING = "Improving"
STATUS_EXPLORING = "Exploring"

# Short, factual one-liners for the compact sections. Only repos listed here can
# appear in Currently Building; anything else falls back to its GitHub
# description, and repos with no description are skipped rather than invented.
SHORT_DESC = {
    "Medical_chatbot": "PDF-grounded RAG service with off-path ingestion workers",
    "TripCaspian": "Conversational commitments turned into tracked obligations",
    "FactLens": "Streaming claim verification with cache-first retrieval",
    "KYC_Face_Verifier": "Document + face verification behind an async job pipeline",
    "HLE-Benchmark-Test": "Resumable multi-model LLM evaluation harness",
    "Trading-bot": "Binance futures execution with a live React dashboard",
    "MagicPin-challenge": "Deterministic merchant messaging engine, no LLM at serve time",
    "Data-Scrapping-Assignment": "Multi-source scraper with trust scoring",
    "ML_Algorithm_from_scratch": "Classical ML algorithms implemented from NumPy up",
    "Apna-Fit": "React storefront with 3D product views and UPI checkout",
    "UPSC-Tracker": "Adaptive study planner across an Express and Spring backend",
    "Dinesh-Sharma": "Personal portfolio site with serverless API routes",
    "tweeter-assistant": "Gemini-backed agent that drafts and posts tweets",
    "ET_Hack": "News intelligence backend with hybrid retrieval and briefings",
    "Intelli-credit": "Credit appraisal pipeline over OCR and document research",
    "ML_Semester_Project": "Regime-aware forecasting with per-regime LightGBM models",
    "Affordmed_assignment": "Layered notification service in Flask",
    "Taxi-Booking": "Taxi booking flow with maps and rebooking",
    "Magic-Pin-AI": "Earlier iteration of the merchant messaging engine",
    "Medibot-frontend-Demo": "Standalone chat front end for the medical RAG API",
    "HLE-Benchmark": "LLM evaluation harness",
}
