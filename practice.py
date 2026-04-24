from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*",],
    allow_methods = ["*"],
    allow_headers= ["*"],
)

class loginData(BaseModel):
    username: str
    password: str

@app.post("/login")
def getData(payload: loginData):
    print(f"Name: {payload.username}, Password: {payload.password}")
    return True    