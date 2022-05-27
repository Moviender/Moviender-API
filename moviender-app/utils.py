from pydantic import BaseModel
from bson import ObjectId
from enum import IntEnum
from firebase_admin import messaging
from surprise import dump
from .dependencies import get_db_client

db = get_db_client()


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


class UserVotesBody(BaseModel):
    uid: str
    votes: list[bool]


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


def get_movielens_id_rating(user_ratings: UserRatings):
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


def get_recommendation(uid: str, friend_uid: str, genres_ids):
    list_of_movies = fetch_movies(uid, friend_uid, genres_ids)
    result_tuple = get_final_list(uid, friend_uid, list_of_movies)
    return [recommendation[0] for recommendation in result_tuple]


def fetch_movies(uid: str, friend_uid: str, genres_ids):
    firstUser = list(db.Ratings.find_one({"uid": uid})["ratings"].keys())
    secondUser = list(db.Ratings.find_one({"uid": friend_uid})["ratings"].keys())

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


def session_status_changed(session_id: str):
    currentSession = get_current_session(session_id)

    recommendations = currentSession["recommendations"]

    result_movies, result_votes = get_result_movies_votes(currentSession, recommendations)

    if result_movies != []:
        return update_session_to_successful(session_id, result_movies)

    elif all_movies_are_voted(len(result_votes), len(recommendations)):
        return update_session_to_failed(session_id)
    else:
        return change_users_state_that_can_keep_voting(session_id, currentSession)


def get_result_movies_votes(currentSession, recommendations):

    all_votes = [currentSession["users_session_info"][user]["voted_movies"] for user in
                 currentSession["users_session_info"].keys()]

    # todo change logic for more than 2 users
    result_votes = [user1 and user2 for user1, user2 in zip(all_votes[0], all_votes[1])]

    result_movies = []

    for index, vote in enumerate(result_votes):
        if vote:
            result_movies.append(recommendations[index])
    return result_movies, result_votes


def get_current_session(session_id: str):
    return db.Sessions.find_one({"_id": ObjectId(session_id)})


def update_session_to_successful(session_id: str, result_movies):
    db.Sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {
            "results": result_movies,
            "state": SessionStatus.SUCCESSFUL_FINISH}}
    )
    return SessionStatus.SUCCESSFUL_FINISH


def all_movies_are_voted(num_result_votes, num_recommendations):
    return num_result_votes == num_recommendations


def user_have_more_movies_to_vote(num_user_votes: int, num_of_recommendations: int):
    return num_user_votes < num_of_recommendations


def update_session_to_failed(session_id: str):
    db.Sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"state": SessionStatus.FAILED_FINISH}}
    )
    return SessionStatus.FAILED_FINISH


def change_users_state_that_can_keep_voting(session_id, currentSession):

    num_of_recommendations = len(currentSession["recommendations"])

    for user in currentSession["users_session_info"].keys():

        num_user_votes = len(currentSession["users_session_info"][user]["voted_movies"])

        if user_have_more_movies_to_vote(num_user_votes, num_of_recommendations):
            db.Sessions.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {f"users_session_info.{user}.state": SessionUserStatus.VOTING},
                    "$inc": {"users_voted": -1}}
            )
    return SessionStatus.WAITING_FOR_VOTES
