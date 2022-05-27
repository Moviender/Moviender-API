from fastapi import APIRouter

from ..dependencies import get_db_client
from ..utils import Status, State, send_friend_request_notification

router = APIRouter()
db = get_db_client()


@router.post("/friend_request/{uid}", tags=["friends"])
async def friend_request(uid: str, friend_username: str):
    try:
        result = list(db.Users.find({"username": friend_username}, {"_id": 0}))[0]
        friend_uid = result["uid"]

        if uid == friend_uid:
            return Status.SAME_UID

        cursor = list(db.Users.find({"uid": uid, f"friend_list.{friend_uid}": {"$exists": True}}))
        if cursor == []:
            token = list(db.Users.find({"uid": friend_uid}))[0]["fcm_token"]
            username = list(db.Users.find({"uid": uid}, {"_id": 0}))[0]["username"]

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

    except IndexError:
        return Status.USERNAME_NOT_FOUND


@router.post("/respond_friend_request/{uid}", tags=["friends"])
async def respond_friend_request(uid: str, friend_uid: str, response: int):
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


@router.post("/delete_friend/{uid}", tags=["friends"])
async def delete_friend(uid: str, friend_uid: str):
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
