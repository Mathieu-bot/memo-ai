from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:adgjmptxw@localhost:5432/memoai")

config = Config()