from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

# The engine manages the actual connection to Postgres. Created once and
# shared by the whole app.
engine = create_engine(config.DATABASE_URL)

# A factory for making new sessions (working conversations with the database).
# We call SessionLocal() once per request, not once for the whole app.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# The base class every table model will inherit from.
Base = declarative_base()


def get_db():
    """Used by FastAPI routes to get a database session, and guarantees it
    gets closed afterward even if the route raises an error."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
