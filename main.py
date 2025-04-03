import sqlite3
from fastapi import FastAPI, HTTPException
from typing import List
from validation import EmailSchema, PersonResponse, PersonCreate, FriendshipCreate, PersonUpdate
import requests

# Database setup
db_path = "people.db"


def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        gender TEXT,
        nationality TEXT,
        age INTEGER
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        person_id INTEGER,
        FOREIGN KEY(person_id) REFERENCES people(id)
    )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friendships (
            person_id INTEGER,
            friend_id INTEGER,
            PRIMARY KEY (person_id, friend_id),
            FOREIGN KEY(person_id) REFERENCES people(id),
            FOREIGN KEY(friend_id) REFERENCES people(id)
        )
        ''')
    conn.commit()
    conn.close()


# App setup
app = FastAPI()


@app.on_event("startup")
def startup_event():
    init_db()


# Utility functions
def fetch_external_data(name: str):
    age_response = requests.get(f"https://api.agify.io/?name={name}")
    gender_response = requests.get(f"https://api.genderize.io/?name={name}")
    nationality_response = requests.get(f"https://api.nationalize.io/?name={name}")

    age = age_response.json().get("age", 0)
    gender = gender_response.json().get("gender", "unknown")
    nationalities = nationality_response.json().get("country", [])
    nationality = nationalities[0]["country_id"]

    return age, gender, nationality


# Endpoints
@app.post("/people/", response_model=PersonResponse)
def create_person(person: PersonCreate):
    age, gender, nationality = fetch_external_data(person.first_name)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO people (first_name, last_name, gender, nationality, age) VALUES (?, ?, ?, ?, ?)",
        (person.first_name, person.last_name, gender, nationality, age)
    )
    conn.commit()
    person_id = cursor.lastrowid

    cursor.execute("SELECT * FROM people WHERE id = ?", (person_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "gender": row[3],
            "nationality": row[4],
            "age": row[5],
            "emails": []
        }
    else:
        raise HTTPException(status_code=500, detail="Error creating person")


@app.get("/people/{last_name}", response_model=List[PersonResponse])
def get_person_by_last_name(last_name: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM people WHERE last_name = ?", (last_name,))
    rows = cursor.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Person not found")

    people = []
    for row in rows:
        cursor.execute("SELECT email FROM emails WHERE person_id = ?", (row[0],))
        emails = cursor.fetchall()
        email_list = [EmailSchema(email=email[0]) for email in emails]
        people.append({
            "id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "gender": row[3],
            "nationality": row[4],
            "age": row[5],
            "emails": email_list
        })

    conn.close()
    return people


@app.get("/people/", response_model=List[PersonResponse])
def list_people():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM people")
    rows = cursor.fetchall()

    people = []
    for row in rows:
        cursor.execute("SELECT email FROM emails WHERE person_id = ?", (row[0],))
        emails = cursor.fetchall()
        email_list = [EmailSchema(email=email[0]) for email in emails]
        people.append({
            "id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "gender": row[3],
            "nationality": row[4],
            "age": row[5],
            "emails": email_list
        })

    conn.close()
    return people

@app.put("/people/{person_id}/")
def update_person_info(person_id: int, person: PersonUpdate):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM people WHERE id = ?", (person_id,))
    person_found = cursor.fetchone()

    if not person_found:
        conn.close()
        raise HTTPException(status_code=404, detail="Person not found")

    cursor.execute("""
    UPDATE people
    SET first_name = ?, last_name = ?, nationality = ?, age = ?
    WHERE id = ?
    """, (person.first_name, person.last_name, person.nationality, person.age, person_id))

    conn.commit()
    conn.close()
    return {"message": "Info has been updated successfully"}



@app.post("/people/{person_id}/email/")
def add_email(person_id: int, email_data: EmailSchema):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM people WHERE id = ?", (person_id,))
    person = cursor.fetchone()

    if not person:
        conn.close()
        raise HTTPException(status_code=404, detail="Person not found")

    try:
        cursor.execute("INSERT INTO emails (email, person_id) VALUES (?, ?)", (email_data.email, person_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already exists")

    conn.close()
    return {"message": "Email added successfully"}


@app.post("/friendships/")
def add_friendship(friendship: FriendshipCreate):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO friendships (person_id, friend_id) VALUES (?, ?)", (friendship.person_id, friendship.friend_id))
        cursor.execute("INSERT INTO friendships (person_id, friend_id) VALUES (?, ?)", (friendship.friend_id, friendship.person_id))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Friendship already exists or invalid person ID")
    finally:
        conn.close()
    return {"message": "Friendship added successfully"}


@app.get("/friends/{person_id}")
def get_friends(person_id: int):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT people.id, people.first_name, people.last_name, people.gender, people.nationality, people.age 
        FROM friendships 
        JOIN people ON friendships.friend_id = people.id 
        WHERE friendships.person_id = ?
    """, (person_id,))
    rows = cursor.fetchall()
    conn.close()

    friends = [
        {
            "id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "gender": row[3],
            "nationality": row[4],
            "age": row[5]
        }
        for row in rows
    ]

    return friends

@app.delete("/people/{person_id}")
def delete_person(person_id: int):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM people
    WHERE id = ?
    """, (person_id,))

    person = cursor.fetchone()

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    cursor.execute("""
    SELECT * FROM friendships
    WHERE person_id = ?
    """, (person_id,))

    friendships = cursor.fetchall()

    if friendships:
        for friendship in friendships:
            cursor.execute("DELETE FROM friendships WHERE person_id = ?", (friendship[0],))
            conn.commit()

    cursor.execute("""
        SELECT * FROM emails
        WHERE person_id = ?
        """, (person_id,))

    emails = cursor.fetchall()

    if emails:
        for email in emails:
            cursor.execute("DELETE FROM emails WHERE person_id = ?", (email[2],))
            conn.commit()

    cursor.execute("DELETE FROM people WHERE id = ?", (person_id,))
    conn.commit()
    conn.close()