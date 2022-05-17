from pydantic import BaseModel
from enum import IntEnum
from firebase_admin import messaging


class User(BaseModel):
    uid: str
    username: str


class Friend(BaseModel):
    uid: str
    username: str
    state: int


class Rating(BaseModel):
    movielens_id: str
    rating: float


class UserRatings(BaseModel):
    uid: str
    ratings: list[Rating]


class State(IntEnum):
    PENDING = 1
    REQUEST = 2
    FRIEND = 3


class Status(IntEnum):
    SUCCESSFUL_FRIEND_REQUEST = 1
    USERNAME_NOT_FOUND = -1
    ALREADY_EXISTS = -2
    SAME_UID = -3
    ACCEPT_REQUEST = 1
    DECLINE_REQUEST = 0



def convert_user_ratings_to_json(user_ratings: UserRatings):
    convertedUserRatings = {"uid": user_ratings.uid}

    ratings = {}
    for movieid_tuple, rating_tuple in user_ratings.ratings:
        ratings[movieid_tuple[1]] = rating_tuple[1]

    convertedUserRatings["ratings"] = ratings

    return convertedUserRatings


def get_movieid_rating(user_ratings: UserRatings):
    movie_id = None
    rating = None

    for movieid_tuple, rating_tuple in user_ratings.ratings:
        rating = rating_tuple[1]
        movie_id = movieid_tuple[1]

    return movie_id, rating


def send_friend_request_notification(username: str, token: str):
    message = messaging.Message(
        data={
            'name': username
        },
        token=token
    )

    response = messaging.send(message)
    # Response is a message ID string.
    print('Successfully sent message:', response)
