from fastapi import FastAPI

app = FastAPI(
    title="FDE Sprint API",
    version="0.1.0",
    description="Day 1: LLM backend",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple check that the server is alive."""
    return {"status": "ok"}