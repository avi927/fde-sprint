# FDE Sprint API

? One or two sentences: what this project is and what it does.

## Tech stack

- Python 3.14, FastAPI, Pydantic
- ? (list the rest)

## Setup

1. Create the repo
2. Create and activate a virtual environment:-
    :-py -3.14 -m venv .venv
    :-.venv\Scripts\activate

3. Install dependencies:-
annotated-doc==0.0.6
annotated-types==0.8.0
anthropic==2.9.0
anyio==4.16.0
click==8.5.1
docstring_parser==0.18.0
fastapi==0.163.1
h11==0.16.0
httpcore2==2.16.2
httptools==0.9.0
httpx2==2.16.2
idna==3.20
jiter==0.19.0
openai==3.52.0
opentelemetry-api==1.45.2
pydantic==2.14.3
pydantic-settings==2.16.3
pydantic_core==2.50.4
python-dotenv==1.2.4
PyYAML==6.0.3
sniffio==1.3.1
starlette==1.10.0
truststore==0.10.5
typing-inspection==0.4.5
typing_extensions==4.16.0
uvicorn==0.54.0
watchfiles==1.3.0
websockets==17.4

4. Copy `.env.example` to `.env` and fill in your keys

## Run
uvicorn app.main:app --reload


Then open http://127.0.0.1:8000/docs for Swagger.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | /health | ? |
| POST | /chat | ? |

## Error codes

| Code | When |
|---|---|
| 422 | ? |
| 429 | ? |
| 502 | ? |
| 503 | ? |
| 504 | ? |

## Known limitations

- Anthropic is not configured yet (no API key), so `provider: "anthropic"` returns 503.
- ? (anything else you noticed)
