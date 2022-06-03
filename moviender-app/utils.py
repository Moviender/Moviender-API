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
    profile_pic_url: str


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


class UserGenrePreferences(BaseModel):
    uid: str
    genres_ids: list[int]


class SessionRequestBody(BaseModel):
    friend_uid: str
    genres_ids: list[int]


class SessionRequestBodySim(BaseModel):
    friend_uid: str
    movielens_id: str


class UserVotesBody(BaseModel):
    uid: str
    votes: list[bool]


class State(IntEnum):
    PENDING = 1
    REQUEST = 2
    FRIEND = 3
    SESSION = 4


class Status(IntEnum):
    SUCCESSFUL_FRIEND_REQUEST = 11
    USERNAME_NOT_FOUND = -10
    ALREADY_EXISTS = -11
    SAME_UID = -12
    ACCEPT_REQUEST = 12
    DECLINE_REQUEST = 10


class SessionStatus(IntEnum):
    WAITING_FOR_VOTES = 20
    SUCCESSFUL_FINISH = 21
    FAILED_FINISH = -20


class SessionUserStatus(IntEnum):
    VOTING = 30
    WAITING = 31
    VOTING_AGAIN = 32


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
                    "$set": {f"users_session_info.{user}.state": SessionUserStatus.VOTING_AGAIN},
                    "$inc": {"users_voted": -1}}
            )
    return SessionStatus.WAITING_FOR_VOTES


def check_if_users_are_in_session(uid, body):
    return db.Users.find_one({"uid": uid, f"friend_list.{body.friend_uid}": State.FRIEND})


def get_similar_movies(movielens_id: str):
    # load a tuple with (prediction, trained-algorithm)
    algo = dump.load("TrainedModels/trainedKNNBaseline.model")
    # get just the algorithm
    algo = algo[1]

    input_movie_inner_id = algo.trainset.to_inner_iid(movielens_id)

    # Retrieve inner ids of the nearest neighbors of input movie
    input_movie_neighbors = algo.get_neighbors(input_movie_inner_id, k=20)

    # Convert inner ids of the neighbors into raw ids
    input_movie_neighbors = [algo.trainset.to_raw_iid(inner_id) for inner_id in input_movie_neighbors]

    return input_movie_neighbors


def fetch_user_unwatched_movies(uid: str):
    watched_movies = list(db.Ratings.find_one({"uid": uid})["ratings"].keys())

    pipeline = [
        {"$match": {"movielens_id": {"$nin": watched_movies}}},
        {"$project": {"_id": 0, "movielens_id": 1, "vote_average": 1, "popularity": 1, "genre_ids": 1, "vote_count": 1,
                      "poster_path": 1}}
    ]

    cursor = db.Movies.aggregate(pipeline)
    cursor = list(cursor)

    return cursor


def get_personal_recommendation(uid: str):
    movies = fetch_user_unwatched_movies(uid)
    genres_preferences = db.Users.find_one({"uid": uid})["genre_preference"]
    movies = normalize_genres_based_on_preferences(movies, genres_preferences)
    movies = calculate_score(movies)

    movies.sort(reverse=True, key=lambda movie: movie["score"])

    return movies[:20]


def normalize_genres_based_on_preferences(movies: list, preferences: list):
    preferences_set = set(preferences)
    for movie in movies:
        movie["genre_score"] = len(preferences_set.intersection(movie["genre_ids"])) / len(movie["genre_ids"])

    return movies


def calculate_score(movies: list):
    genres_weight = 0.4
    vote_average_weight = 0.22
    vote_count_weight = 0.18
    popularity_weight = 0.20

    vote_average_max = max(movies, key=lambda movie: movie["vote_average"])["vote_average"]
    vote_count_max = max(movies, key=lambda movie: movie["vote_count"])["vote_count"]
    popularity_max = max(movies, key=lambda movie: movie["popularity"])["popularity"]
    genre_score_max = max(movies, key=lambda movie: movie["genre_score"])["genre_score"]

    for movie in movies:
        movie_average_score = (movie["vote_average"] / vote_average_max) * vote_average_weight
        movie_vote_count_score = (movie["vote_count"] / vote_count_max) * vote_count_weight
        movie_popularity_score = (movie["popularity"] / popularity_max) * popularity_weight
        movie_genres_score = (movie["genre_score"] / genre_score_max) * genres_weight
        movie["score"] = movie_genres_score + movie_popularity_score + movie_average_score + movie_vote_count_score

    return movies
