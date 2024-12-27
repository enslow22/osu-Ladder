from typing import Union
from fastapi import FastAPI
from ORM import ORM
from models import RegisteredUser

app = FastAPI()
orm = ORM()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {'user': orm.session.get(RegisteredUser, user_id)}

@app.get("/users/{}")

@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}