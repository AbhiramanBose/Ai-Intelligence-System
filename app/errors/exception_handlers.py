from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(request: Request, exc: SQLAlchemyError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "DATABASE_UNAVAILABLE",
                "message": "The database is temporarily unavailable.",
                "path": request.url.path,
            },
        )
