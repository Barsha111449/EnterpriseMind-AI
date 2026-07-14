from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.database.session import engine
from backend.app.api.registration import router as registration_router
from backend.app.api.authentication import router as authentication_router
from backend.app.api.documents import router as documents_router
from backend.app.api.search import router as search_router
app = FastAPI(
    title="EnterpriseMind AI",
    version="0.1.0",
    description="A secure company knowledge assistant",
)
app.include_router(registration_router)
app.include_router(authentication_router)
app.include_router(documents_router)
app.include_router(search_router)

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


@app.get("/health/database")
def database_health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

        return {
            "status": "healthy",
            "database": str(database_name),
        }

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        ) from exc