import pymongo
from fastapi import APIRouter
from ..dependencies import get_db_client
from ..utils import Friend, User, UserRatings, convert_user_ratings_to_json, UserGenrePreferences

router = APIRouter()
db = get_db_client()


@router.get("/initialized/{uid}", tags=["users"])
async def is_user_initialized(uid: str):
    try:
        result = db.Users.find_one({"uid": uid}, {"_id": 0, "is_user_initialized": 1})["is_user_initialized"]
        return result
    except IndexError:
        print(f"User with {uid} not found")


@router.get("/friends/{uid}", tags=["users"])
async def get_friend_list(uid: str):
    friend_list = db.Users.find_one({"uid": uid})["friend_list"]
    friends = []
    for friend_uid in friend_list.keys():
        # get username from friend uid
        friend_username = db.Users.find_one({"uid": friend_uid})["username"]

        # create Friend object
        friend = Friend(uid=friend_uid, username=friend_username, state=friend_list[friend_uid])

        friends.append(friend)

    return friends


@router.post("/user", tags=["users"])
async def insert_user(user: User):
    try:
        result = db.Users.insert_one({
            "uid": user.uid,
            "username": user.username,
            "profile_pic": user.profile_pic_url,
            "is_user_initialized": False,
            "genre_preference": [],
            "friend_list": {}})
    except pymongo.errors.DuplicateKeyError:
        return "Key already exists"
    if result.acknowledged:
        return "inserted"
    else:
        return "Error"


@router.post("/fcm_token/{uid}", tags=["users"])
async def update_user_fcm_token(uid: str, token: str):
    db.Users.update_one(
        {"uid": uid},
        {"$set": {"fcm_token": token}}
    )


@router.post("/userInitialization", tags=["users"])
async def insert_ratings(user_ratings: UserRatings):
    json_ratings = convert_user_ratings_to_json(user_ratings=user_ratings)

    db.Ratings.insert_one(json_ratings)

    db.Users.update_one(
        {"uid": user_ratings.uid},
        {"$set": {"is_user_initialized": True}}
    )


@router.post("/userGenrePreference/", tags=["users"])
async def insert_genre_preference(user_genre_pref: UserGenrePreferences):
    db.Users.update_one(
        {"uid": user_genre_pref.uid},
        {"$set": {"genre_preference": user_genre_pref.genres_ids}}
    )
