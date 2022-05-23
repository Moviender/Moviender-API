import os

import firebase_admin
from fastapi import FastAPI
from .routers import users, movies, friends, sessions

default_app = firebase_admin.initialize_app()

app = FastAPI()
app.include_router(users.router)
app.include_router(movies.router)
app.include_router(friends.router)
app.include_router(sessions.router)

print(os.getcwd())


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


