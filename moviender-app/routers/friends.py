import bson
from bson import ObjectId
from fastapi import APIRouter

from ..dependencies import get_db_client
from ..utils import Status, State, send_friend_request_notification, find_session_id

router = APIRouter()
db = get_db_client()


@router.post("/friend_request/{uid}", tags=["friends"])
async def friend_request(uid: str, friend_username: str):
    result = db.Users.find_one({"username": friend_username}, {"_id": 0})

    if result is None:
        return Status.USERNAME_NOT_FOUND

    friend_uid = result["uid"]

    if uid == friend_uid:
        return Status.SAME_UID

    cursor = db.Users.find_one({"uid": uid, f"friend_list.{friend_uid}": {"$exists": True}})
    if cursor is None:

        # check if friend account is initialized
        current_friend = db.Users.find_one({"uid": friend_uid})
        if not current_friend["is_user_initialized"]:
            return Status.USERNAME_NOT_FOUND


        username = db.Users.find_one({"uid": uid})["username"]

        token = current_friend["fcm_token"]

        if token is not None:
            send_friend_request_notification(username, token)

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


@router.post("/respond_friend_request/{uid}", tags=["friends"])
async def respond_friend_request(uid: str, friend_uid: str, response: int):
    try:
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
        return True
    except:
        return False


@router.post("/delete_friend/{uid}", tags=["friends"])
async def delete_friend(uid: str, friend_uid: str):
    try:

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

        session_id = find_session_id(uid, friend_uid)

        db.Sessions.delete_one({"_id": ObjectId(session_id)})
        return True
    except bson.errors.InvalidId:
        return True
    except Exception:
        return False
