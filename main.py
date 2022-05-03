import pymongo.errors
import utils
from typing import List
from fastapi import FastAPI, Query
from pymongo import MongoClient

app = FastAPI()
client = MongoClient('mongodb://localhost:27017')
db = client.Moviender

PAGE_SIZE = 15


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.post("/user")
async def insert_user(user: utils.User):
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
    pipeline = [
        {"$sample": {"size": 15}},
        {"$project": {"_id": 0, "movielens_id": 1, "genre_ids": 1, "poster_path": 1, "title": 1, "overview": 1}}
    ]

    cursor = db.Movies.aggregate(pipeline)

    return [movie_metadata for movie_metadata in cursor]


@app.post("/userInitialization")
async def insert_ratings(user_ratings: utils.UserRatings):
    json_ratings = utils.convert_user_rating_to_json(user_ratings=user_ratings)

    db.Ratings.insert_one(json_ratings)


@app.get("/movies/{page}")
def get_movies(page: int = 1, genres: List[int] = Query([])):
    if genres:
        match_genres = {"$or": [{"genre_ids": genre_id} for genre_id in genres]}
    else:
        match_genres = {}
    pipeline = [
        {"$match": match_genres},
        {"$sort": {"popularity": -1}},
        {"$project": {"_id": 0, "movielens_id": 1, "genre_ids": 1, "poster_path": 1,
                      "title": 1, "overview": 1, "release_date": 1, "vote_average": 1}},
        {"$skip": PAGE_SIZE * (page - 1)},
        {"$limit": PAGE_SIZE}
    ]
    cursor = db.Movies.aggregate(pipeline)

    return list(cursor)
