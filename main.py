import pymongo.errors
import utils
from fastapi import FastAPI
from pymongo import MongoClient

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.post("/user")
async def insert_user(user: utils.User):
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
        {"$sample": {"size": 15}},
        {"$project": {"_id": 0, "movielens_id": 1, "genre_ids": 1, "poster_path": 1, "title": 1, "overview": 1}}
    ]

    cursor = db.Movies.aggregate(pipeline)

    return [movie_metadata for movie_metadata in cursor]


@app.post("/userInitialization")
async def insert_ratings(user_ratings: utils.UserRatings):
    client = MongoClient('mongodb://localhost:27017')
    db = client.MovienderDB

    json_ratings = utils.convert_user_rating_to_json(user_ratings=user_ratings)

    db.Ratings.insert_one(json_ratings)