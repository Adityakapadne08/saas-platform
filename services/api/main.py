from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt
from typing import Optional
import os

# --- Config ---
SECRET_KEY = "change-this-in-production-use-secrets-manager"
ALGORITHM = "HS256"

# --- App ---
app = FastAPI(title="API Service", version="1.0.0")
bearer_scheme = HTTPBearer()

# --- In-memory resource store ---
resources_db = {}

# --- Models ---
class ResourceCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ResourceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner: str
    tenant: str

# --- Token validation ---
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# --- Routes ---
@app.get("/health")
def health():
    return {"status": "healthy", "service": "api"}

@app.post("/resources")
def create_resource(
    resource: ResourceCreate,
    tenant: str,
    current_user: str = Depends(get_current_user)
):
    resource_id = f"{tenant}-{len(resources_db) + 1}"
    resources_db[resource_id] = {
        "id": resource_id,
        "name": resource.name,
        "description": resource.description,
        "owner": current_user,
        "tenant": tenant
    }
    return resources_db[resource_id]

@app.get("/resources")
def list_resources(
    tenant: str,
    current_user: str = Depends(get_current_user)
):
    tenant_resources = {
        k: v for k, v in resources_db.items()
        if v["tenant"] == tenant
    }
    return {"tenant": tenant, "resources": tenant_resources, "requested_by": current_user}

@app.delete("/resources/{resource_id}")
def delete_resource(
    resource_id: str,
    current_user: str = Depends(get_current_user)
):
    if resource_id not in resources_db:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resources_db[resource_id]["owner"] != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to delete this resource")
    del resources_db[resource_id]
    return {"message": f"Resource {resource_id} deleted"}