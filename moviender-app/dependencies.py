from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.getenv("DB_CONNECTION_STRING"))
db = client.MovienderDB
PAGE_SIZE = 15


def get_db_client():
    return db


def get_page_size():
    return PAGE_SIZE
