from sqlalchemy import create_engine
from sqlmodel import SQLModel
import os
from dotenv import load_dotenv

# .env file ko load karne ke liye
load_dotenv()

# Ab variable read karein
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    """
    Create database tables in the correct order to respect foreign key constraints.
    """
    # Import all models to ensure they're registered with SQLModel


    # Create all tables
    SQLModel.metadata.create_all(engine)