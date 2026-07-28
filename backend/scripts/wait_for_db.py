import os
import sys
import time
import psycopg2


def wait_for_db():
    db_url = os.getenv(
        "DATABASE_URL", "postgresql://leadgen_user:leadgen_pass@db:5432/leadgen_db"
    )
    print(f"Checking database connection at: {db_url}")

    if db_url.startswith("sqlite"):
        print("SQLite database detected. Skipping network check.")
        return

    max_retries = 30
    for i in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(db_url)
            conn.close()
            print("Database is up and accepting connections!")
            return
        except psycopg2.OperationalError as e:
            print(f"Database not ready yet (attempt {i}/{max_retries}): {e}")
            time.sleep(2)

    print("Error: Database connection timed out after multiple attempts.")
    sys.exit(1)


if __name__ == "__main__":
    wait_for_db()
