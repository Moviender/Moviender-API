from pydantic import BaseModel


class User(BaseModel):
    uid: str


class Rating(BaseModel):
    movielens_id: str
    rating: float


class UserRatings(BaseModel):
    uid: str
    ratings: list[Rating]


def convert_user_rating_to_json(user_ratings: UserRatings):

    convertedUserRatings = {"uid": user_ratings.uid}

    ratings = {}
    for movieid_tuple, rating_tuple in user_ratings.ratings:
        ratings[movieid_tuple[1]] = rating_tuple[1]

    convertedUserRatings["ratings"] = ratings

    return convertedUserRatings