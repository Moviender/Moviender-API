from bson import ObjectId
from fastapi import APIRouter

from ..dependencies import get_db_client
from ..utils import SessionStatus, State, SessionRequestBody, UserVotesBody, get_recommendation, SessionUserStatus, \
    session_status_changed, SessionRequestBodySim, check_if_users_are_in_session, get_similar_movies, find_session_id

router = APIRouter()
db = get_db_client()


@router.get("/session_id", tags=["sessions"])
async def get_session_id(uid: str, friend_uid: str):
    session_id = find_session_id(uid, friend_uid)
    return session_id


@router.get("/user_state/{session_id}", tags=["sessions"])
async def get_user_state(session_id: str, uid: str):
    cursor = db.Sessions.find_one({"_id": ObjectId(session_id)})["users_session_info"][uid]["state"]

    return cursor


@router.get("/session_state/{session_id}", tags=["sessions"])
async def get_session_state(session_id: str):
    cursor = db.Sessions.find_one({"_id": ObjectId(session_id)})["state"]

    return cursor


@router.get("/session_user_votes/{session_id}", tags=["sessions"])
async def get_user_num_votes(session_id: str, uid: str):
    cursor = db.Sessions.find_one({"_id": ObjectId(session_id)})

    num_voted_movies = len(cursor["users_session_info"][uid]["voted_movies"])
    return num_voted_movies


@router.get("/session_results/{session_id}", tags=["sessions"])
async def get_session_result_list(session_id: str):
    session = db.Sessions.find_one({"_id": ObjectId(session_id)})
    if session["state"] == SessionStatus.SUCCESSFUL_FINISH:
        return session["results"]
    else:
        return []


@router.post("/session_recommendations/{uid}", tags=["sessions"])
async def init_friends_session_recommendations(uid: str, body: SessionRequestBody):
    inSession = check_if_users_are_in_session(uid, body)

    if inSession is None:
        return {"session_id": None}

    top_n_recommendation = get_recommendation(uid, body.friend_uid, body.genres_ids)
    result = db.Sessions.insert_one({
        "users_in_session": [uid, body.friend_uid],
        "users_session_info": {uid: {"state": SessionUserStatus.VOTING, "voted_movies": []},
                               body.friend_uid: {"state": SessionUserStatus.VOTING, "voted_movies": []}},
        "results": [],
        "users_voted": 0,
        "recommendations": top_n_recommendation,
        "is_active": True,
        "state": SessionStatus.WAITING_FOR_VOTES
    })

    db.Users.update_one(
        {"uid": uid},
        {"$set": {f"friend_list.{body.friend_uid}": State.SESSION}}
    )
    db.Users.update_one(
        {"uid": body.friend_uid},
        {"$set": {f"friend_list.{uid}": State.SESSION}}
    )

    return {"session_id": str(result.inserted_id)}


@router.post("/session_sim/{uid}", tags=["sessions"])
async def init_friends_session_sim(uid: str, body: SessionRequestBodySim):
    inSession = check_if_users_are_in_session(uid, body)

    if inSession is None:
        return {"session_id": None}

    top_n_similar_movies = get_similar_movies(body.movielens_id)

    result = db.Sessions.insert_one({
        "users_in_session": [uid, body.friend_uid],
        "users_session_info": {uid: {"state": SessionUserStatus.VOTING, "voted_movies": []},
                               body.friend_uid: {"state": SessionUserStatus.VOTING, "voted_movies": []}},
        "results": [],
        "users_voted": 0,
        "recommendations": top_n_similar_movies,
        "is_active": True,
        "state": SessionStatus.WAITING_FOR_VOTES
    })

    db.Users.update_one(
        {"uid": uid},
        {"$set": {f"friend_list.{body.friend_uid}": State.SESSION}}
    )
    db.Users.update_one(
        {"uid": body.friend_uid},
        {"$set": {f"friend_list.{uid}": State.SESSION}}
    )

    return {"session_id": str(result.inserted_id)}


@router.post("/vote_in_session/{session_id}", tags=["sessions"])
async def vote_in_session(session_id: str, body: UserVotesBody):
    uid = body.uid
    voted_movies = body.votes

    # insert user votes
    # update user session status
    # update number of user that has voted
    db.Sessions.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$set": {f"users_session_info.{uid}.voted_movies": voted_movies,
                     f"users_session_info.{uid}.state": SessionUserStatus.WAITING},
            "$inc": {"users_voted": 1}}
    )

    users_voted = db.Sessions.find_one({"_id": ObjectId(session_id)})["users_voted"]

    if users_voted == 2:
        return session_status_changed(session_id)
    else:
        return SessionStatus.WAITING_FOR_VOTES


@router.post("/close_session/{session_id}", tags=["sessions"])
async def close_session(session_id: str):
    try:
        cursor = db.Sessions.find_one({"_id": ObjectId(session_id)})
        user1 = cursor["users_in_session"][0]
        user2 = cursor["users_in_session"][1]

        db.Users.update_one(
            {"uid": user1},
            {"$set": {f"friend_list.{user2}": State.FRIEND}}
        )
        db.Users.update_one(
            {"uid": user2},
            {"$set": {f"friend_list.{user1}": State.FRIEND}}
        )

        db.Sessions.delete_one({"_id": ObjectId(session_id)})
        return True
    except:
        return False
