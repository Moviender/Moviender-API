import pymongo.errors
from fastapi import FastAPI
from pymongo import MongoClient
from pydantic import BaseModel

app = FastAPI()


class User(BaseModel):
    uid: str


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.post("/user")
async def insert_user(user: User):
    client = MongoClient('mongodb://localhost:27017')
    db = client.MovienderDB

    try:
        result = db.Users.insert_one({"uid": user.uid})
    except pymongo.errors.DuplicateKeyError:
        return "Key already exists"

    if result.acknowledged:
        return "inserted"
    else:
        return "Error"

@app.get("/starter")
async def get_starter():
    client = MongoClient('mongodb://localhost:27017')
    db = client.MovienderDB

    pipeline = [
        {"$sample": {"size": 15} },
        {"$project": {"_id": 0, "imdb_id": 1, "genre_ids": 1, "poster_path": 1, "title": 1, "overview": 1}}
    ]

    cursor = db.Movies.aggregate(pipeline)

    return [movie_metadata for movie_metadata in cursor]