from fastapi import FastAPI, HTTPException, Depends,status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from pydantic import BaseModel
from .db import engine
import json
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = "super-secret-key-schimba-l"
ALGORITHM = "HS256"

app = FastAPI()

ACCESS_TOKEN_EXPIRE_MINUTES = 120
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_user_from_db(username: str):
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT id, username, password, role FROM superhero_api.users WHERE username=:u"),
        {"u": username},
        ).mappings().first()
    return user


def create_access_token(username: str, role: str):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def require_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")

        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = get_user_from_db(username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_admin(user=Depends(require_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@app.get("/")
def root():
    return {"status": "ok"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = get_user_from_db(form.username)

    if not user:
        raise HTTPException(status_code=401, detail="Wrong username or password")

    if not pwd_context.verify(form.password, user["password"]):
        raise HTTPException(status_code=401, detail="Wrong username or password")

    token = create_access_token(user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

class RegisterRequest(BaseModel):
    username: str
    password: str

@app.post("/register")
def register_user(data: RegisterRequest):
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE username=:u"),
            {"u": data.username}
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="User exists")

        hashed = pwd_context.hash(data.password)

        conn.execute(
            text("""
                INSERT INTO users (username, password, role)
                VALUES (:u, :p, 'user')
            """),
            {"u": data.username, "p": hashed}
        )
        conn.commit()

    return {"status": "ok"}

class WorkModel(BaseModel):
    base: str | None = None
    occupation: str | None = None

class ItemCreate(BaseModel):
    name: str
    image: str | None = None
    work: WorkModel | None = None

@app.post("/items")
def create_item(payload: ItemCreate, user=Depends(require_admin)):
    data = payload.model_dump()

    with engine.connect() as conn:
        r = conn.execute(
            text("INSERT INTO data (data) VALUES (:data)"),
            {"data": json.dumps(data)}
        )
        conn.commit()
        new_id = r.lastrowid

    return {"id": new_id, "status": "ok"}


@app.get("/items")
def get_items(
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    base: str | None = None,
    occupation: str | None = None,
    user=Depends(require_user)

):
    offset = (page - 1) * page_size

    where = []
    params = {"limit": page_size, "offset": offset}

    # SEARCH general (q)
    if q and q.strip():
        params["q"] = f"%{q.strip()}%"
        where.append("""
          (
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.name')) LIKE :q
            OR JSON_UNQUOTE(JSON_EXTRACT(data, '$.work.base')) LIKE :q
            OR JSON_UNQUOTE(JSON_EXTRACT(data, '$.work.occupation')) LIKE :q
          )
        """)

    # FILTER: base
    if base and base.strip():
        params["base"] = f"%{base.strip()}%"
        where.append("JSON_UNQUOTE(JSON_EXTRACT(data, '$.work.base')) LIKE :base")

    # FILTER: occupation
    if occupation and occupation.strip():
        params["occ"] = f"%{occupation.strip()}%"
        where.append("JSON_UNQUOTE(JSON_EXTRACT(data, '$.work.occupation')) LIKE :occ")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT id, data FROM data {where_sql} LIMIT :limit OFFSET :offset"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    items = []
    for r in rows:
        d = r["data"]
        if isinstance(d, str):
            d = json.loads(d)
        items.append({"id": r["id"], "name": d.get("name"), "image": d.get("image")})

    return {"page": page, "page_size": page_size, "q": q, "base": base, "occupation": occupation, "items": items}

@app.get("/items/{item_id}")
def get_item(
        item_id: int,
        user=Depends(require_user)
):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, data FROM data WHERE id = :id"),
            {"id": item_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Item not found")

    d = row["data"]
    if isinstance(d, str):
        d = json.loads(d)

    return {
        "id": row["id"],
        "name": d.get("name"),
        "work": d.get("work"),   # obiectul work din JSON
        "image": d.get("image")  # opțional; îl poți afișa și în detaliu
    }

@app.post("/admin/items")
def insert_item(data: dict, user=Depends(require_admin)):
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO data (data) VALUES (:data)"),
            {"data": json.dumps(data)}
        )
        conn.commit()
    return {"status": "inserted"}

@app.put("/items/{item_id}")
def update_item(item_id: int, payload: dict, user=Depends(require_admin)):
    # payload trebuie să fie exact JSON-ul item-ului: {name, image, work:{base,occupation}}
    with engine.begin() as conn:
        res = conn.execute(
            text("UPDATE superhero_api.data SET data=:data WHERE id=:id"),
            {"id": item_id, "data": json.dumps(payload, ensure_ascii=False)},
        )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


@app.delete("/items/{item_id}")
def delete_item(item_id: int, user=Depends(require_admin)):
    with engine.begin() as conn:
        res = conn.execute(
            text("DELETE FROM superhero_api.data WHERE id=:id"),
            {"id": item_id},
        )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


