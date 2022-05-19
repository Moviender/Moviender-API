import re
from typing import List

import pymongo.errors
from fastapi import FastAPI, Query
from pymongo import MongoClient
from utils import State, Status
import firebase_admin
import utils

app = FastAPI()
client = MongoClient('mongodb://localhost:27017')
db = client.MovienderDB

PAGE_SIZE = 15
EXCLUDE_ID = {"_id": 0}

default_app = firebase_admin.initialize_app()


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


@app.get("/initialized/{uid}")
async def is_user_initialized(uid: str):
    try:
        result = list(db.Users.find({"uid": uid}, {"_id": 0, "is_user_initialized": 1}))[0]["is_user_initialized"]

        print(result)

        return result
    except IndexError:
        print(f"User with {uid} not found")


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
        result = db.Users.insert_one({
            "uid": user.uid,
            "username": user.username,
            "is_user_initialized": False,
            "friend_list": {}})
    except pymongo.errors.DuplicateKeyError:
        return "Key already exists"
    if result.acknowledged:
        return "inserted"
    else:
        return "Error"


@app.post("/fcm_token/{uid}")
async def update_user_fcm_token(uid: str, token: str):
    db.Users.update_one(
        {"uid": uid},
        {"$set": {"fcm_token": token}}
    )


@app.post("/userInitialization")
async def insert_ratings(user_ratings: utils.UserRatings):
    json_ratings = utils.convert_user_ratings_to_json(user_ratings=user_ratings)

    db.Ratings.insert_one(json_ratings)

    db.Users.update_one(
        {"uid": user_ratings.uid},
        {"$set": {"is_user_initialized": True}}
    )


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

        if uid == friend_uid:
            return Status.SAME_UID

        cursor = list(db.Users.find({"uid": uid, f"friend_list.{friend_uid}": {"$exists": True}}))
        if cursor == []:
            token = list(db.Users.find({"uid": friend_uid}))[0]["fcm_token"]
            username = list(db.Users.find({"uid": uid}, EXCLUDE_ID))[0]["username"]

            utils.send_friend_request_notification(username, token)

            db.Users.update_one(
                {"uid": uid},
                {"$set": {f"friend_list.{friend_uid}": State.PENDING}}
            )
            db.Users.update_one(
                {"uid": friend_uid},
                {"$set": {f"friend_list.{uid}": State.REQUEST}}
            )
            return Status.SUCCESSFUL_FRIEND_REQUEST
        else:
            return Status.ALREADY_EXISTS

    except IndexError:
        return Status.USERNAME_NOT_FOUND


@app.post("/respond_friend_request/{uid}")
def respond_friend_request(uid: str, friend_uid: str, response: int):
    if response == Status.ACCEPT_REQUEST:
        db.Users.update_one(
            {"uid": uid},
            {"$set": {f"friend_list.{friend_uid}": State.FRIEND}}
        )
        db.Users.update_one(
            {"uid": friend_uid},
            {"$set": {f"friend_list.{uid}": State.FRIEND}}
        )
    elif response == Status.DECLINE_REQUEST:
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


@app.post("/delete_friend/{uid}")
def delete_friend(uid: str, friend_uid: str):
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


@app.post("/session/{uid}")
def init_friends_session(uid: str, friend_uid: str, genres_ids: list[int]):
    # Check if user have an opened session with current friend
    inSession = list(db.Users.find({"uid": uid, f"friend_list.{friend_uid}": 3})) == []
    print(inSession)
    if not inSession:
        db.Users.update_one(
            {"uid": uid},
            {"$set": {f"friend_list.{friend_uid}": State.SESSION}}
        )
        db.Users.update_one(
            {"uid": friend_uid},
            {"$set": {f"friend_list.{uid}": State.SESSION}}
        )
        top_n_recommendation = utils.get_recommendation(uid, friend_uid, genres_ids, db)
        db.Sessions.insert_one({
            "user_in_session": [uid, friend_uid],
            "users_votes": {},
            "results": [],
            "users_voted": 0,
            "recommendations": top_n_recommendation,
            "is_active": True,
            "state": utils.SessionStatus.WAITING_FOR_VOTES
        })
