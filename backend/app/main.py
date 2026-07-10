from fastapi import FastAPI

app = FastAPI(
    title="EnterpriseMind AI",
    version="0.1.0",
    description="A secure company knowledge assistant",
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Welcome to EnterpriseMind AI",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "EnterpriseMind AI API",
    }