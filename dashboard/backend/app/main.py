
import os

import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

app = FastAPI()


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        connection_timeout=5,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/health-db")
def health_db():
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE(), 1")
        database_name, result = cursor.fetchone()
        cursor.close()
        connection.close()

        return {
            "status": "connected",
            "database": database_name,
            "test_query": result,
        }

    except Exception as e:
        print(f"Database connection error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"{type(e).__name__}: {e}",
        )
