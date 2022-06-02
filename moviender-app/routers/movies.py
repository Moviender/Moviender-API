import re
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Query

from ..dependencies import get_db_client, get_page_size
from ..utils import UserRatings, get_movielens_id_rating, get_personal_recommendation

router = APIRouter()
db = get_db_client()
PAGE_SIZE = get_page_size()


@router.get("/starter", tags=["movies"])
async def get_starter():
    pipeline = [
        {"$sample": {"size": 15}},
        {"$project": {"_id": 0, "movielens_id": 1, "poster_path": 1}}
    ]

    cursor = db.Movies.aggregate(pipeline)

    return [movie_metadata for movie_metadata in cursor]


@router.get("/session_movies/{session_id}", tags=["movies"])
async def get_session_movies(session_id: str, uid: str, next_page_key: int = None):
    if next_page_key is None:
        next_page_key = 0

    session = db.Sessions.find_one({"_id": ObjectId(session_id)})

    num_voted_movies = len(session["users_session_info"][uid]["voted_movies"])
    recommendations = session["recommendations"][num_voted_movies:]

    skip = 10 * next_page_key
    limit = (10 * next_page_key) + 10
    recommendations = recommendations[skip:limit]
    result = []
    for recommendation in recommendations:
        pipeline = [
            {"$match": {"movielens_id": recommendation}},
            {"$project": {"_id": 0, "movielens_id": 1, "genre_ids": 1, "title": 1, "overview": 1, "release_date": 1,
                          "vote_average": 1, "poster_path": 1}}
        ]
        result.append(list(db.Movies.aggregate(pipeline))[0])

    if len(recommendations) < 10:
        next_page_key = None
    else:
        next_page_key += 1

    return {"movies": result, "next_page_key": next_page_key}


@router.get("/movies/{page}", tags=["movies"])
async def get_movies(page: int = 1, genres: List[int] = Query([])):
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


@router.get("/movie_details/{movie_id}", tags=["movies"])
async def get_movie_details(movie_id: str, uid: str):
    match_movie_id = {"movielens_id": movie_id}
    pipeline = [
        {"$match": match_movie_id},
        {"$project": {"_id": 0, "poster_path": 1, "genre_ids": 1, "title": 1, "overview": 1, "release_date": 1,
                      "vote_average": 1}}
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


@router.get("/movie_rating/{movie_id}", tags=["movies"])
async def get_movie_rating(movie_id: str, uid: str):
    match = {"uid": uid, f"ratings.{movie_id}": {"$exists": True}}

    pipeline = [
        {"$match": match},
        {"$project": {"_id": 0, f"ratings.{movie_id}": 1}}
    ]

    cursor = list(db.Ratings.aggregate(pipeline))

    if cursor != []:
        rating = cursor[0]["ratings"][movie_id]
    else:
        rating = 0.0

    return rating


@router.get("/search", tags=["movies"])
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


@router.get("/user_recommendations/{page}", tags=["movies"])
async def get_user_recommendations(page: int, uid: str):
    recommended_movies = get_personal_recommendation(uid)

    results = [{"movielens_id": movie["movielens_id"], "poster_path": movie["poster_path"]} for movie in
               recommended_movies]

    skip = PAGE_SIZE * (page - 1)
    limit = (PAGE_SIZE * (page - 1)) + PAGE_SIZE
    return results[skip:limit]

@router.post("/rating", tags=["movies"])
async def update_rating(user_rating: UserRatings):
    uid = user_rating.uid
    movie_id, rating = get_movielens_id_rating(user_rating)

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
