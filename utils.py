from pydantic import BaseModel
from enum import IntEnum
from firebase_admin import messaging
#from surprise import dump
from surprise import dump


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


class SessionRequestBody(BaseModel):
    friend_uid: str
    genres_ids: list[int]


class State(IntEnum):
    PENDING = 1
    REQUEST = 2
    FRIEND = 3
    SESSION = 4


class Status(IntEnum):
    SUCCESSFUL_FRIEND_REQUEST = 1
    USERNAME_NOT_FOUND = -1
    ALREADY_EXISTS = -2
    SAME_UID = -3
    ACCEPT_REQUEST = 1
    DECLINE_REQUEST = 0


class SessionStatus(IntEnum):
    WAITING_FOR_VOTES = 0
    SUCCESSFUL_FINISH = 1
    FAILED_FINISH = -1


class SessionUserStatus(IntEnum):
    VOTING = 0
    WAITING = 1


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


def get_recommendation(uid: str, friend_uid: str, genres_ids, db):
    list_of_movies = fetch_movies(uid, friend_uid, genres_ids, db)
    result_tuple = get_final_list(uid, friend_uid, list_of_movies)
    return [recommendation[0] for recommendation in result_tuple]


def fetch_movies(uid: str, friend_uid: str, genres_ids, db):
    firstUser = list(list(db.Ratings.find({"uid": uid}))[0]["ratings"].keys())
    secondUser = list(list(db.Ratings.find({"uid": friend_uid}))[0]["ratings"].keys())

    mergedMoviesList = list(set(firstUser + secondUser))

    if genres_ids:
        match_options = {"$and": [
            {"genre_ids": {"$in": genres_ids}},
            {"movielens_id": {"$nin": mergedMoviesList}}]}
    else:
        match_options = {"movielens_id": {"$nin": mergedMoviesList}}

    pipeline = [
        {"$match": match_options},
        {"$project": {"_id": 0, "movielens_id": 1}}
    ]

    cursor = db.Movies.aggregate(pipeline)
    cursor = list(cursor)
    return [movie_id["movielens_id"] for movie_id in cursor]


def get_final_list(uid: str, friend_uid: str, list_of_movies):
    # load a tuple with (prediction, trained-algorithm)
    algo = dump.load("TrainedModels/trainedSVDAlgo.model")
    # get just the algorithm
    algo = algo[1]

    user_combined_predictions = []
    for movie_id in list_of_movies:
        user_pred = algo.predict(uid, movie_id)
        friend_user_pred = algo.predict(friend_uid, movie_id)
        user_combined_predictions.append((movie_id, (user_pred.est + friend_user_pred.est) / 2.0))

    user_combined_predictions.sort(key=lambda x: x[1], reverse=True)
    if len(user_combined_predictions) > 50:
        user_combined_predictions = user_combined_predictions[0:50]
    return user_combined_predictions
