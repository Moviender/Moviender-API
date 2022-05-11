import pymongo.errors
from pymongo.collation import Collation

import utils
from typing import List
from fastapi import FastAPI, Query
from pymongo import MongoClient

import re

app = FastAPI()
client = MongoClient('mongodb://localhost:27017')
db = client.MovienderDB

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
        {"$project": {"_id": 0, "movielens_id": 1, "poster_path": 1}}
    ]

    cursor = db.Movies.aggregate(pipeline)

    return [movie_metadata for movie_metadata in cursor]


@app.post("/userInitialization")
async def insert_ratings(user_ratings: utils.UserRatings):
    json_ratings = utils.convert_user_ratings_to_json(user_ratings=user_ratings)

    db.Ratings.insert_one(json_ratings)


@app.post("/rating")
async def update_rating(user_rating: utils.UserRatings):
    uid = user_rating.uid
    movie_id, rating = utils.get_movieid_rating(user_rating)

    if rating != 0:
        db.Ratings.update_one(
            {"uid": uid},
            {"$set": {f"ratings.{movie_id}": float(rating)}}
        )
    else:
        db.Ratings.update_one(
            {"uid": uid},
            {"$unset": {f"ratings.{movie_id}": 1}},
            False, True
        )



@app.get("/movies/{page}")
def get_movies(page: int = 1, genres: List[int] = Query([])):
    if genres:
        match_genres = {"$or": [{"genre_ids": genre_id} for genre_id in genres]}
    else:
        match_genres = {}
    pipeline = [
        {"$match": match_genres},
        {"$sort": {"popularity": -1}},
        {"$project": {"_id": 0, "movielens_id": 1, "poster_path": 1}},
        {"$skip": PAGE_SIZE * (page - 1)},
        {"$limit": PAGE_SIZE}
    ]
    cursor = db.Movies.aggregate(pipeline)

    return list(cursor)


@app.get("/movie_details/{movie_id}")
def get_movie_details(movie_id: str, uid: str):
    match_movie_id = {"movielens_id": movie_id}
    pipeline = [
        {"$match": match_movie_id},
        {"$project": {"_id": 0, "genre_ids": 1, "title": 1, "overview": 1, "release_date": 1, "vote_average": 1}}
    ]

    cursor = list(db.Movies.aggregate(pipeline))
    result = cursor[0]

    match_uid = {"uid": uid, f"ratings.{movie_id}": {"$exists": True}}
    pipeline = [
        {"$match": match_uid},
        {"$project": {"_id": 0, f"ratings.{movie_id}": 1}}
    ]

    cursor = list(db.Ratings.aggregate(pipeline))
    if cursor != []:
        rating = cursor[0]["ratings"][movie_id]
    else:
        rating = 0.0

    result["user_rating"] = rating
    return result

@app.get("/search")
async def get_search_results(title: str = ""):
    regx = re.compile(f".*{title}.*", re.IGNORECASE)

    pipeline = [
        {"$match": {"title": {"$regex": regx}}},
        {"$sort": {"popularity": -1}},
        {"$project": {"_id": 0, "movielens_id": 1, "poster_path": 1, "title": 1}},
        {"$limit": 20}
    ]

    cursor = list(db.Movies.aggregate(pipeline))

    return cursor