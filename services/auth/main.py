from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
# Auth Service v2
# --- Config ---
SECRET_KEY = "change-this-in-production-use-secrets-manager"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

# --- App ---
app = FastAPI(title="Auth Service", version="1.1.0")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

# --- In-memory user store (DB in real world) ---
fake_users_db = {}

# --- Models ---
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

# --- Helpers ---
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# --- Routes ---
@app.get("/health")
def health():
    return {"status": "healthy", "service": "auth"}

@app.post("/register")
def register(req: RegisterRequest):
    if req.username in fake_users_db:
        raise HTTPException(status_code=400, detail="User already exists")
    fake_users_db[req.username] = hash_password(req.password)
    return {"message": "User registered successfully"}

@app.post("/login")
def login(req: LoginRequest):
    hashed = fake_users_db.get(req.username)
    if not hashed or not verify_password(req.password, hashed):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(req.username)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/verify")
def verify(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return {"valid": True, "username": payload.get("sub")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")