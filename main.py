import re
from typing import List

import pymongo.errors
from fastapi import FastAPI, Query
from pymongo import MongoClient

import utils

app = FastAPI()
client = MongoClient('mongodb://localhost:27017')
db = client.MovienderDB

PAGE_SIZE = 15
EXCLUDE_ID = {"_id": 0}

PENDING = 1
REQUEST = 2
FRIEND = 3
SUCCESSFUL_FRIEND_REQUEST = 1
USERNAME_NOT_FOUND = -1
ALREADY_EXISTS = -2
ACCEPT_REQUEST = 1
DECLINE_REQUEST = 0


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/starter")
async def get_starter():
    pipeline = [
        {"$sample": {"size": 15}},
        {"$project": {"_id": 0, "movielens_id": 1, "poster_path": 1}}
    ]

    cursor = db.Movies.aggregate(pipeline)

    return [movie_metadata for movie_metadata in cursor]


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


@app.get("/friends/{uid}")
async def get_friend_list(uid: str):
    cursor = list(db.Users.find({"uid": uid}))[0]["friend_list"]
    friends = []
    for friend_uid in cursor.keys():
        # get username from friend uid
        friend_username = list(db.Users.find({"uid": friend_uid}))[0]["username"]

        # create Friend object
        friend = utils.Friend(uid=friend_uid, username=friend_username, state=cursor[friend_uid])

        friends.append(friend)

    return friends


@app.post("/user")
async def insert_user(user: utils.User):
    try:
        result = db.Users.insert_one({"uid": user.uid, "username": user.username})
    except pymongo.errors.DuplicateKeyError:
        return "Key already exists"

    if result.acknowledged:
        return "inserted"
    else:
        return "Error"


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


@app.post("/friend_request/{uid}")
def friend_request(uid: str, friend_username: str):
    try:
        result = list(db.Users.find({"username": friend_username}, EXCLUDE_ID))[0]
        friend_uid = result["uid"]

        cursor = list(db.Users.find({"uid": uid, f"friend_list.{friend_uid}": {"$exists": True}}))
        if cursor == []:
            db.Users.update_one(
                {"uid": uid},
                {"$set": {f"friend_list.{friend_uid}": PENDING}}
            )
            db.Users.update_one(
                {"uid": friend_uid},
                {"$set": {f"friend_list.{uid}": REQUEST}}
            )
            return SUCCESSFUL_FRIEND_REQUEST
        else:
            return ALREADY_EXISTS

    except IndexError:
        return USERNAME_NOT_FOUND


@app.post("/respond_friend_request/{uid}")
def friend_request(uid: str, friend_uid: str, response: int):
    if response == ACCEPT_REQUEST:
        db.Users.update_one(
            {"uid": uid},
            {"$set": {f"friend_list.{friend_uid}": FRIEND}}
        )
        db.Users.update_one(
            {"uid": friend_uid},
            {"$set": {f"friend_list.{uid}": FRIEND}}
        )
    elif response == DECLINE_REQUEST:
        db.Users.update_one(
            {"uid": uid},
            {"$unset": {f"friend_list.{friend_uid}": 1}},
            False, True
        )
        db.Users.update_one(
            {"uid": friend_uid},
            {"$unset": {f"friend_list.{uid}": 1}},
            False, True
        )
