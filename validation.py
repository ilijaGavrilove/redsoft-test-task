from pydantic import BaseModel, EmailStr
from typing import List

# Pydantic schemas
class EmailSchema(BaseModel):
    email: EmailStr


class PersonCreate(BaseModel):
    first_name: str
    last_name: str

class PersonUpdate(BaseModel):
    first_name: str
    last_name: str
    nationality: str
    age: int

class PersonResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    nationality: str
    age: int
    emails: List[EmailSchema] = []


class FriendshipCreate(BaseModel):
    person_id: int
    friend_id: int