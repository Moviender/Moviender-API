from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client.MovienderDB
PAGE_SIZE = 15


def get_db_client():
    return db


def get_page_size():
    return PAGE_SIZE
