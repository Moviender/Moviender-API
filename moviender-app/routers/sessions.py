from bson import ObjectId
from fastapi import APIRouter

from ..dependencies import get_db_client
from ..utils import SessionStatus, State, SessionRequestBody, get_recommendation, SessionUserStatus

router = APIRouter()
db = get_db_client()


@router.get("/session_id", tags=["sessions"])
async def get_session_id(uid: str, friend_uid: str):
    cursor = str(list(
        db.Sessions.find({"$or": [{"users_in_session": [uid, friend_uid]}, {"users_in_session": [friend_uid, uid]}]}))[
                     0]["_id"])

    return cursor


@router.get("/session_state/{session_id}", tags=["sessions"])
async def get_session_state(session_id: str):
    cursor = list(db.Sessions.find({"_id": ObjectId(session_id)}))[0]["state"]

    return cursor


@router.post("/session/{uid}", tags=["sessions"])
def init_friends_session(uid: str, body: SessionRequestBody):
    # Check if user have an opened session with current friend
    inSession = list(db.Users.find({"uid": uid, f"friend_list.{body.friend_uid}": 3})) == []
    print(inSession)
    if not inSession:

        top_n_recommendation = get_recommendation(uid, body.friend_uid, body.genres_ids, db)
        result = db.Sessions.insert_one({
            "users_in_session": [uid, body.friend_uid],
            "users_session_info": {uid: {"state": SessionUserStatus.VOTING, "voted_movies": []},
                                   body.friend_uid: {"state": SessionUserStatus.VOTING, "voted_movies": []}},
            "users_votes": {},
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
    else:
        return None
