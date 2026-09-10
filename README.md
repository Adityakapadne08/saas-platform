# SaaS Platform

Multi-tenant SaaS infrastructure platform built with Docker, Kubernetes, Helm, Terraform, Jenkins, ArgoCD, and Prometheus.


Why virtual environment?
If you install packages directly with pip, they install globally on your machine. Every Python project then shares the same packages. This causes version conflicts. A virtual environment keeps packages isolated per project — exactly like how containers isolate dependencies. Same concept, different level.

Why requirements.txt?
When Docker builds your container image, it needs to know exactly which packages to install inside the container. It cannot use your local venv. pip freeze captures every installed package with its exact version number — Docker will use this file to recreate the exact same environment inside the container. This is how you guarantee "works on my machine" = "works in production."

In windows to create a new file eg - New-Item services\auth\main.py -ItemType File


services\auth\__init__.py

Leave it completely empty. Just create the file, save it.

Why?
This tells Python that services/auth is a package. Without it, the uvicorn services.auth.main:app command we ran earlier works locally but will cause import errors inside Docker. Empty file, but critical.

Docker file understanding - 
Stage 1 — Builder

dockerfile
FROM python:3.11-slim AS builder

We use python:3.11-slim not python:3.11. Slim is a minimal version — no unnecessary tools, smaller attack surface, faster to pull. AS builder names this stage so Stage 2 can reference it.

dockerfile
WORKDIR /app

Sets the working directory inside the container. Every command after this runs from /app. Same as cd /app in Linux.

dockerfile
COPY requirements.txt .

Copies only requirements.txt first — not the full code. This is intentional. Docker builds in layers and caches each one. If you copy code and requirements together, any code change rebuilds the entire pip install layer. Copying requirements separately means pip install layer is cached unless requirements actually change.

dockerfile
RUN pip install --no-cache-dir -r requirements.txt

Installs packages inside the container. --no-cache-dir tells pip not to store download cache — keeps the image smaller.

Stage 2 — Production

dockerfile
FROM python:3.11-slim AS production

Fresh clean image. We start over — this is the multi-stage build pattern. Stage 1 was just for installing packages.

dockerfile
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

Creates a non-root user. By default Docker runs as root — that is a security risk. If someone exploits your app they get root inside the container. Running as appuser limits the damage.

dockerfile
COPY --from=builder /usr/local/lib/python3.11/site-packages ...

Copies only the installed packages from Stage 1 into Stage 2. We get the packages without carrying over pip, build tools, or cache. This is why multi-stage builds exist — lean final image.

dockerfile
COPY main.py .

Copies only your application code. Not requirements.txt, not __pycache__, not anything else.

dockerfile
USER appuser

Switches to non-root user. Everything after this line runs as appuser, including the server.

dockerfile
EXPOSE 8001

Documents which port the container listens on. Does not actually open the port — that happens at docker run. It is documentation for humans and orchestration tools like Kubernetes.

dockerfile
HEALTHCHECK ...

Docker will run this command every 30 seconds. If it fails 3 times the container is marked unhealthy. Kubernetes uses this to decide whether to restart the container or route traffic to it.

dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

The command that starts your server when the container launches. 0.0.0.0 means accept connections from any IP — required inside a container, otherwise only localhost inside the container can reach it.

Why two stages and not one?

Single stage = build tools + pip cache + everything stays in the final image = larger, more vulnerable image.

Two stages = final image has only what it needs to run. Nothing else. This is the standard pattern in production.




Good habit. Here is the documentation — add this to your personal notes, not the project README:

Docker Layer Caching — How and Why
The Problem

Every docker build runs each instruction in the Dockerfile top to bottom. Without caching, a single line change in main.py would reinstall all packages from scratch — wasting 40+ seconds on every build.

How Docker Cache Works

Docker builds in layers. Each instruction creates one layer:

dockerfile
FROM python:3.11-slim AS builder        # Layer 1 — base image
WORKDIR /app                            # Layer 2 — set working dir
COPY requirements.txt .                 # Layer 3 — copy dependencies file
RUN pip install -r requirements.txt     # Layer 4 — install packages (HEAVY)
COPY main.py .                          # Layer 5 — copy application code

Docker caches each layer. On rebuild, it checks — did anything change that affects this layer?

If NO → use cached layer, skip execution
If YES → rebuild this layer AND every layer below it
The Critical Decision — Copy Order

Wrong way:

dockerfile
COPY . .                          # copies everything together
RUN pip install -r requirements.txt

Any change to main.py invalidates the COPY layer → pip install reruns every time.

Right way:

dockerfile
COPY requirements.txt .           # copy ONLY requirements first
RUN pip install -r requirements.txt   # this layer only invalidates if requirements.txt changes
COPY main.py .                    # code changes only affect THIS layer

Now changing main.py only rebuilds the last layer. Pip install stays cached.

Real Numbers From This Project
Scenario	Time
First build — no cache	48 seconds
Second build — code unchanged	2.4 seconds
After changing main.py only	~3 seconds (pip cached)
After changing requirements.txt	~48 seconds (pip reruns)
Why This Matters in Jenkins CI/CD

Jenkins builds your image on every single Git push. A monorepo with 5 services = 5 builds per push. Without cache optimization that is 5 × 48s = 4 minutes just on pip installs. With proper layer ordering it is under 15 seconds total.

Multi-Stage Build — Why Two Stages
dockerfile
# Stage 1 — Builder (has pip, build tools, cache)
FROM python:3.11-slim AS builder
RUN pip install -r requirements.txt     # installs everything including build tools

# Stage 2 — Production (clean, minimal)
FROM python:3.11-slim AS production
COPY --from=builder /usr/local/lib/python3.11/site-packages .  # only the packages
COPY main.py .                          # only the code

Stage 1 is a throwaway — it exists only to install packages cleanly.
Stage 2 copies only what it needs from Stage 1 — no pip, no build tools, no cache.

Result: final image is smaller, has fewer binaries an attacker could exploit, and contains nothing that is not needed at runtime.

Security Layer — Non-Root User
dockerfile
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser

Docker containers run as root by default. If your app is exploited, the attacker gets root inside the container. Running as appuser means they get a locked-down user with no permissions. This is a mandatory practice in production — any security audit will flag root containers immediately.

Health Check
dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"

Docker pings /health every 30 seconds. If it fails 3 consecutive times the container is marked unhealthy. Kubernetes uses this status to decide whether to restart the pod or stop routing traffic to it. Without a health check, Kubernetes has no way to know if your app crashed silently.



we build the API Service — the second microservice.

What does the API service do?
It is a simple resource management API. Before serving any request it validates the JWT token issued by the Auth service. This is how real microservices work — one service issues tokens, every other service verifies them. No service trusts a request without a valid token.



Helm Charts

Helm is how you package and deploy your services to Kubernetes. Instead of writing raw Kubernetes YAML for every environment, you write one Helm chart with variables — and pass different values for staging vs prod vs tenant-A vs tenant-B.




----------------------------------------------------------------------

# SaaS Platform — Project Notes & Documentation
> Personal reference — DevOps project by Aditya Kapadne  
> Stack: Python · FastAPI · Docker · Kubernetes · Helm · Terraform · Jenkins · ArgoCD · Prometheus

---

## Table of Contents
1. [Project Goal](#1-project-goal)
2. [Tech Stack Overview](#2-tech-stack-overview)
3. [Environment Setup](#3-environment-setup)
4. [Project Structure](#4-project-structure)
5. [Git & GitHub Setup](#5-git--github-setup)
6. [Auth Service](#6-auth-service)
7. [API Service](#7-api-service)
8. [Docker — Core Concepts](#8-docker--core-concepts)
9. [Docker Compose](#9-docker-compose)
10. [Kubernetes Setup](#10-kubernetes-setup)
11. [Helm — Setup](#11-helm--setup)

---

## 1. Project Goal

Build a **Multi-Tenant SaaS Infrastructure Platform** — not just deploying an app, but building the platform layer that a real SaaS product would run on.

Each "tenant" (customer) gets:
- Isolated Kubernetes namespace
- Independent deployment pipeline
- Separate resource management
- Per-tenant monitoring dashboards

**Why this project is SDE-3 level:**
- You write the services yourself (not copied from YouTube)
- Terraform uses proper module structure (not flat files)
- Jenkins pipeline uses `git diff` to selectively build only changed services
- Security is built in — not added as an afterthought

---

## 2. Tech Stack Overview

| Layer | Tool | Purpose |
|---|---|---|
| Services | Python + FastAPI | Auth and API microservices |
| Containers | Docker | Package and run services |
| Orchestration | Kubernetes + Helm | Deploy and manage containers at scale |
| Infra as Code | Terraform | Provision AWS infrastructure |
| CI/CD | Jenkins | Build, test, deploy pipeline |
| GitOps | ArgoCD | Pull-based deployment from Git |
| Secrets | AWS Secrets Manager + External Secrets Operator | Zero hardcoded credentials |
| Security | Trivy + OPA/Gatekeeper + NetworkPolicy | Image scanning, admission control, isolation |
| Observability | Prometheus + Grafana + Loki | Metrics, dashboards, logs |

---

## 3. Environment Setup

### Tools Required
| Tool | Version Used |
|---|---|
| Windows | 10/11 |
| Docker Desktop | 29.3.1 |
| Python | 3.14.3 |
| Git | 2.53.0 |
| VS Code | Latest |
| Helm | 4.2.3 |
| kubectl | Comes with Docker Desktop |

### Python Virtual Environment

**Why venv?**
Installs packages per project instead of globally. Prevents version conflicts across projects. Same concept as Docker containers — isolated environments.

```powershell
# Create virtual environment
python -m venv venv

# Activate it (PowerShell)
venv\Scripts\Activate.ps1

# You will see (venv) prefix in terminal when active
(venv) PS C:\Users\DELL\Downloads\saas-platform>
```

### Install Python Packages

```powershell
pip install fastapi uvicorn python-jose[cryptography] passlib[bcrypt]
```

| Package | Purpose |
|---|---|
| fastapi | Web framework for building APIs |
| uvicorn | ASGI server that runs FastAPI |
| python-jose | JWT token creation and validation |
| passlib[bcrypt] | Password hashing |

### Lock Dependencies

```powershell
pip freeze > services\auth\requirements.txt
```

**Why `requirements.txt`?**
Docker cannot use your local venv. This file captures every package with exact version numbers. Docker uses it to recreate identical environment inside the container. Guarantees "works on my machine" = "works in production."

---

## 4. Project Structure

```
saas-platform/
├── services/
│   ├── auth/           ← Auth microservice
│   └── api/            ← API microservice
├── terraform/
│   ├── modules/
│   │   ├── tenant/     ← Reusable per-tenant infra
│   │   ├── eks-cluster/
│   │   └── monitoring/
│   └── envs/
│       ├── staging/
│       └── prod/
├── k8s/
│   ├── base/
│   └── tenants/
├── helm/
│   ├── auth/           ← Helm chart for auth service
│   └── api/            ← Helm chart for api service
├── jenkins/            ← Jenkins pipeline definitions
├── monitoring/
│   ├── dashboards/
│   └── alerts/
├── docs/
│   └── decisions/      ← Architecture decision records
├── docker-compose.yml
└── .gitignore
```

**Why Git does not show empty folders:**
Git tracks files, not folders. Empty folders are invisible on GitHub. They appear only when files are added inside them.

---

## 5. Git & GitHub Setup

### Initial Git Configuration

```powershell
git config --global user.email "youremail@gmail.com"
git config --global user.name "Your Name"
```

Must be done once. Every commit is stamped with this identity.

### Initialize Repository

```powershell
git init
git add .gitignore
git commit -m "chore: initial project structure and gitignore"
```

### Commit Message Convention — Conventional Commits

```
feat:   new feature
fix:    bug fix
chore:  maintenance, no feature change
docs:   documentation only
refactor: code restructure, no behavior change
```

Professional teams follow this format. Keeps history readable.

### Connect to GitHub

```powershell
git remote add origin https://github.com/username/saas-platform.git
git branch -M main
git push -u origin main
```

| Command | Meaning |
|---|---|
| `git remote add origin <url>` | Tells local git where GitHub repo lives |
| `git branch -M main` | Renames branch from master to main |
| `git push -u origin main` | Pushes to GitHub, sets default upstream |

### GitHub Authentication — Personal Access Token (PAT)

GitHub stopped accepting passwords in 2021. Use PAT instead:

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token → check `repo` scope → copy immediately
3. Use in remote URL:

```powershell
git remote set-url origin https://USERNAME:TOKEN@github.com/USERNAME/repo.git
```

**Security:** Remove token from URL after pushing. Never commit a token to Git.

### .gitignore

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.env
venv/
*.egg-info/

# Terraform
*.tfstate
*.tfstate.backup
.terraform/
.terraform.lock.hcl
*.tfvars

# Docker
*.log

# OS
.DS_Store
Thumbs.db

# VS Code
.vscode/
```

**Why this matters:** Prevents accidentally committing secrets (`.env`), terraform state files (contain sensitive infra details), build artifacts, and local IDE config.

---

## 6. Auth Service

**Location:** `services/auth/`

**What it does:**
Handles user registration and login. Returns a JWT token on successful login. Every other service validates this token before serving requests.

### Files

```
services/auth/
├── main.py           ← FastAPI application
├── requirements.txt  ← Locked dependencies
├── __init__.py       ← Empty — makes directory a Python package
└── Dockerfile        ← Container definition
```

**Why `__init__.py` is empty but required:**
Tells Python that `services/auth` is a package. Without it, `uvicorn services.auth.main:app` throws import errors inside Docker even if it works locally.

### main.py

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

# --- Config ---
SECRET_KEY = "change-this-in-production-use-secrets-manager"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

# --- App ---
app = FastAPI(title="Auth Service", version="1.0.0")
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
```

### Run Locally (without Docker)

```powershell
uvicorn services.auth.main:app --reload --port 8001
```

Auto-generated docs available at: `http://localhost:8001/docs`

### Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | Health check — used by Docker and Kubernetes |
| POST | /register | Register a new user |
| POST | /login | Login and receive JWT token |
| GET | /verify | Validate a JWT token |

---

## 7. API Service

**Location:** `services/api/`

**What it does:**
Resource management API. Validates JWT token from Auth service before every request. Manages resources per tenant. Shows how microservices trust tokens from a central auth service.

### main.py

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt
from typing import Optional

SECRET_KEY = "change-this-in-production-use-secrets-manager"
ALGORITHM = "HS256"

app = FastAPI(title="API Service", version="1.0.0")
bearer_scheme = HTTPBearer()
resources_db = {}

class ResourceCreate(BaseModel):
    name: str
    description: Optional[str] = None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@app.get("/health")
def health():
    return {"status": "healthy", "service": "api"}

@app.post("/resources")
def create_resource(resource: ResourceCreate, tenant: str, current_user: str = Depends(get_current_user)):
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
def list_resources(tenant: str, current_user: str = Depends(get_current_user)):
    tenant_resources = {k: v for k, v in resources_db.items() if v["tenant"] == tenant}
    return {"tenant": tenant, "resources": tenant_resources, "requested_by": current_user}

@app.delete("/resources/{resource_id}")
def delete_resource(resource_id: str, current_user: str = Depends(get_current_user)):
    if resource_id not in resources_db:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resources_db[resource_id]["owner"] != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to delete this resource")
    del resources_db[resource_id]
    return {"message": f"Resource {resource_id} deleted"}
```

---

## 8. Docker — Core Concepts

### Dockerfile (Auth Service)

```dockerfile
# Stage 1 — Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2 — Production stage
FROM python:3.11-slim AS production

# Create non-root user — security best practice
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

COPY main.py .

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Dockerfile Line by Line

| Line | Explanation |
|---|---|
| `FROM python:3.11-slim AS builder` | Base image. `slim` = minimal, no unnecessary tools. `AS builder` names this stage |
| `WORKDIR /app` | Sets working directory inside container. Like `cd /app` |
| `COPY requirements.txt .` | Copy ONLY requirements first — enables layer caching for pip install |
| `RUN pip install --no-cache-dir` | Install packages. `--no-cache-dir` keeps image smaller |
| `FROM python:3.11-slim AS production` | Fresh clean image — Stage 2 starts over |
| `RUN groupadd && useradd appuser` | Create non-root user for security |
| `COPY --from=builder ...site-packages` | Copy only installed packages from Stage 1 |
| `USER appuser` | Switch to non-root. All commands after run as appuser |
| `EXPOSE 8001` | Documents which port the container listens on |
| `HEALTHCHECK` | Docker pings /health every 30s. 3 failures = container marked unhealthy |
| `CMD ["uvicorn", ...]` | Command that starts server when container launches |
| `--host 0.0.0.0` | Accept connections from any IP — required inside containers |

### Why Multi-Stage Build?

```
Single stage → build tools + pip cache + everything in final image = large, vulnerable
Two stages  → final image has only runtime dependencies = small, secure
```

Result: **62.4MB** instead of 400MB+

### Docker Layer Caching

```dockerfile
# WRONG — code change forces pip to reinstall everything
COPY . .
RUN pip install -r requirements.txt

# RIGHT — requirements change and code change are independent layers
COPY requirements.txt .          # Layer A — invalidates only if requirements.txt changes
RUN pip install -r requirements.txt  # Layer B — cached unless Layer A changed
COPY main.py .                   # Layer C — only this rebuilds on code change
```

**Real numbers from this project:**
| Scenario | Build Time |
|---|---|
| First build — no cache | 48 seconds |
| Second build — nothing changed | 2.4 seconds |
| After changing main.py only | ~3 seconds |
| After changing requirements.txt | ~48 seconds |

### Security — Non-Root User

Docker runs as root by default. If the app is exploited, attacker gets root inside the container.

```dockerfile
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
```

Running as `appuser` = attacker gets a locked-down user with no permissions. Mandatory in production — security audits flag root containers immediately.

### Docker Commands

```powershell
# Build image
docker build -t saas-auth:v1 services\auth

# Run container
docker run -d --name auth-service -p 8001:8001 saas-auth:v1

# List running containers
docker ps

# Stop container
docker stop auth-service

# Remove container
docker rm auth-service

# List images
docker images
```

### Image vs Container

```
Image     = class definition    (saas-auth:v1)
Container = instance of class   (auth-service)

docker stop → pause the instance
docker rm   → delete the instance
Image is never affected by stop/rm
```

---

## 9. Docker Compose

**File:** `docker-compose.yml` (in project root)

**Purpose:** Run multiple containers together with networking, dependencies, and health checks defined in one file.

```yaml
services:
  auth:
    image: saas-auth:v1
    container_name: auth-service
    ports:
      - "8001:8001"
    networks:
      - saas-network
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    restart: unless-stopped

  api:
    image: saas-api:v1
    container_name: api-service
    ports:
      - "8002:8002"
    networks:
      - saas-network
    depends_on:
      auth:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    restart: unless-stopped

networks:
  saas-network:
    driver: bridge
```

### Key Concepts

`depends_on: condition: service_healthy` — API service only starts after Auth service passes health check. Not just "started" — actually healthy.

`networks: saas-network` — Both containers share a private network. They can reach each other by container name. From outside only the mapped ports are accessible.

`restart: unless-stopped` — Container auto-restarts on crash. Does not restart if manually stopped.

### Compose Commands

```powershell
docker compose up -d      # Start all services in background
docker compose down       # Stop and remove all containers
docker compose ps         # List service status
docker compose logs auth  # View logs for a specific service
```

---

## 10. Kubernetes Setup

Enabled via Docker Desktop → Settings → Kubernetes → Enable Kubernetes.

```powershell
# Verify cluster is running
kubectl get nodes

# Expected output:
NAME                    STATUS   ROLES           AGE     VERSION
desktop-control-plane   Ready    control-plane   3m45s   v1.36.1
```

**Why local Kubernetes before AWS EKS?**
Test everything locally before paying for cloud. Docker Desktop gives a real single-node cluster — same kubectl commands work on both.

---

## 11. Helm — Setup

Helm is the package manager for Kubernetes. Instead of writing raw K8s YAML for every environment, write one chart with variables — pass different values for staging vs prod vs each tenant.

### Install Helm on Windows

```powershell
winget install Helm.Helm

# Add to PATH if not auto-detected
$env:PATH += ";C:\Users\DELL\AppData\Local\Microsoft\WinGet\Links"
[System.Environment]::SetEnvironmentVariable("PATH", $env:PATH, "User")

# Verify
helm version
```

### Create Helm Chart

```powershell
helm create helm\auth
```

### Chart Structure

```
helm/auth/
├── Chart.yaml          ← Metadata: name, version, description
├── values.yaml         ← All configurable values (image, port, replicas)
├── charts/             ← Subchart dependencies
└── templates/
    ├── deployment.yaml ← How your pod runs
    ├── service.yaml    ← How pod is exposed inside cluster
    ├── ingress.yaml    ← How traffic enters from outside
    ├── serviceaccount.yaml ← K8s identity for pod
    ├── _helpers.tpl    ← Reusable template functions
    └── NOTES.txt       ← Shown after helm install
```

---

## Commits So Far

| Commit | Message | Files |
|---|---|---|
| eb241c5 | chore: initial project structure and gitignore | .gitignore |
| 43d32fe | first commit | README.md |
| e0a6e23 | docs: fix README | README.md |
| 2cbb101 | feat: add auth service with Dockerfile | services/auth/* |
| b24f6e8 | feat: add api service and docker-compose | services/api/*, docker-compose.yml |

---

## What Comes Next

- [ ] Customize Helm charts for auth and api services
- [ ] Deploy to local Kubernetes using Helm
- [ ] Terraform — AWS VPC + EKS cluster setup
- [ ] Jenkins — monorepo CI pipeline with selective builds
- [ ] ArgoCD — GitOps deployment
- [ ] AWS Secrets Manager + External Secrets Operator
- [ ] Trivy image scanning in pipeline
- [ ] OPA/Gatekeeper admission policies
- [ ] NetworkPolicy — tenant isolation
- [ ] Prometheus + Grafana — per-tenant monitoring
- [ ] Loki — centralized logging
- [ ] Architecture diagram (Excalidraw)



* helm\auth\templates\_helpers.tpl
What is this file?
A library of reusable template functions shared across all other templates in the chart. It is the only file in Helm that starts with an underscore _ — that underscore tells Helm "do not render this as a Kubernetes resource." It is helper code only, never sent to Kubernetes.

Why do we need it?
Without helpers, every template file would repeat the same logic for generating names and labels. Five template files × the same 10 lines of label logic = 50 lines of duplicated code. Change the naming pattern → update 5 files. With helpers — change once here, all templates follow automatically. Same principle as writing reusable functions in application code.

How does it work?
Helm uses Go templating. {{- define "function.name" -}} creates a named function. {{ include "function.name" . }} calls it anywhere. The . passes the current context — all values, chart metadata, and release information — into the function.

Block by Block:

yaml
{{- define "auth.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

Simplest helper. Returns the chart name from Chart.yaml — auth. Truncated to 63 characters because Kubernetes label values have a 63 character limit. trimSuffix "-" removes a trailing dash if truncation cuts a word mid-hyphen. Called everywhere a short chart name is needed.

yaml
{{- define "auth.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

The most important helper. Generates the full name used for every Kubernetes resource — Deployment name, Service name, Ingress name.

yaml
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}

If someone sets fullnameOverride: my-custom-name in values, use that directly. Gives operators full control over naming when needed.

yaml
{{- $name := default .Chart.Name .Values.nameOverride }}

$name is a local variable. default means — use .Values.nameOverride if set, otherwise fall back to .Chart.Name which is auth. So $name = "auth" unless overridden.

yaml
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}

If the release name already contains the chart name — for example release is auth-staging and chart name is auth — just use the release name. Avoids ugly duplication like auth-staging-auth.

yaml
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}

Otherwise combine release name + chart name. helm install staging ./helm/auth → fullname = staging-auth. This becomes the name of every Kubernetes resource created by this chart.

yaml
{{- define "auth.labels" -}}
helm.sh/chart: {{ include "auth.name" . }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "auth.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
tenant: {{ .Values.tenant }}
{{- end }}

Standard Kubernetes recommended labels applied to every resource. These are not arbitrary — the app.kubernetes.io/ prefix is the official Kubernetes label standard followed by all major tools.

helm.sh/chart — which chart and version created this resource. Used by helm list and monitoring tools to identify Helm-managed resources.

app.kubernetes.io/name — the application name. Used by Prometheus, Grafana, and kubectl selectors.

app.kubernetes.io/instance — the release name. Differentiates multiple deployments of the same chart. staging-auth vs prod-auth — same chart, different instances.

app.kubernetes.io/version — your app version from Chart.yaml appVersion. Quoted because version numbers with dots can be misread as floats by YAML parsers.

app.kubernetes.io/managed-by: Helm — tells everyone this resource is managed by Helm. Do not edit manually — changes will be overwritten on next helm upgrade.

tenant: {{ .Values.tenant }} — our custom addition. This single label is what enables:

Prometheus to scrape per-tenant metrics
Grafana to filter dashboards by tenant
NetworkPolicy to enforce tenant isolation
kubectl get all -l tenant=tenant-a to list all resources for one tenant
yaml
{{- define "auth.selectorLabels" -}}
app.kubernetes.io/name: {{ include "auth.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

Minimal subset of labels used by Service to find pods and by Deployment to manage pods. Intentionally smaller than auth.labels — selector labels must be stable and unique. They cannot change after the Deployment is created. Extra labels like helm.sh/chart include the version number which changes on every upgrade — putting that in a selector would break the Deployment on every helm upgrade.

Two labels is enough to uniquely identify pods belonging to this specific release of this chart.

yaml
{{- define "auth.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "auth.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

Determines what name to use for the ServiceAccount.

if .Values.serviceAccount.create — if Helm is creating the ServiceAccount:
Use serviceAccount.name from values if provided. If empty string, fall back to the fullname — staging-auth.

else — if Helm is NOT creating the ServiceAccount (reusing an existing one):
Use serviceAccount.name from values if provided. If empty, fall back to default — the cluster's default ServiceAccount.

This flexibility matters in enterprise environments where a platform team pre-creates ServiceAccounts with specific RBAC rules and helm charts must reference them rather than create their own.

The {{- -}} whitespace control explained once clearly:

{{ }}    render, keep all surrounding whitespace
{{- }}   render, strip whitespace BEFORE this tag
{{ -}}   render, strip whitespace AFTER this tag
{{- -}}  render, strip whitespace on both sides

Without -, Helm templates produce YAML full of blank lines from the template logic itself. The dashes keep the rendered YAML clean and valid.


* deployment.yaml

# What is this file?
# The most important file in the entire Helm chart. It tells Kubernetes how to run your application — which image, how many copies, what resources, security rules, and health checks. Without this, nothing deploys.

# Why does it look like this and not plain YAML?
# Because it is a template. Every {{ }} is a placeholder that Helm fills in from values.yaml before sending to Kubernetes. What Kubernetes actually receives is plain YAML — Helm does the substitution in between.


# Block by Block:

# yaml
# apiVersion: apps/v1
# kind: Deployment

# Every Kubernetes resource starts with these two. apiVersion tells which K8s API group handles this. kind is the resource type. Together they tell K8s — "this is a Deployment, process it accordingly."

# yaml
# metadata:
#   name: {{ include "auth.fullname" . }}
#   namespace: {{ .Values.namespace }}

# name — generated by the auth.fullname helper. If you run helm install staging-auth ./helm/auth, the Deployment gets named staging-auth. Release name is built into the resource name automatically.

# namespace — pulled from values. This is the multi-tenancy mechanism. --set namespace=tenant-a deploys everything into the tenant-a namespace, completely isolated from other tenants.

# yaml
#   labels:
#     {{- include "auth.labels" . | nindent 4 }}

# Applies all standard labels to the Deployment. nindent 4 means — add a newline first, then indent 4 spaces. Required because YAML is whitespace-sensitive. Without correct indentation the entire file breaks.

# yaml
# spec:
#   replicas: {{ .Values.replicaCount }}

# How many identical pods to run simultaneously. Kubernetes guarantees this number is always maintained. Pod dies → new one starts. Node dies → pods reschedule to other nodes. This is what makes Kubernetes different from just running Docker.

# yaml
#   selector:
#     matchLabels:
#       {{- include "auth.selectorLabels" . | nindent 6 }}

# Tells the Deployment which pods it owns. Pods with matching labels belong to this Deployment. This cannot be changed after creation — if you need to change it you must delete and recreate the Deployment. This is why selector labels are kept minimal and stable.

# yaml
#   template:
#     metadata:
#       labels:
#         {{- include "auth.labels" . | nindent 8 }}
#     spec:

# Everything under template describes the pod itself. The labels here must include the selector labels — this is how the Deployment finds and manages its own pods. Pod labels and selector labels must match, otherwise the Deployment manages zero pods.

# yaml
#       securityContext:
#         runAsNonRoot: true
#         runAsUser: 1000
#         fsGroup: 2000

# Pod-level security — applies to all containers in the pod.

# runAsNonRoot: true — Kubernetes rejects the pod if any container tries to run as root. This is cluster-level enforcement, stronger than just the Dockerfile USER instruction.

# runAsUser: 1000 — run as UID 1000, which is the appuser we created in the Dockerfile. Must match.

# fsGroup: 2000 — any files created by the pod belong to group 2000. Needed when mounting volumes — ensures the process can read/write mounted files.

# yaml
#       containers:
#         - name: auth
#           image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
#           imagePullPolicy: {{ .Values.image.pullPolicy }}

# name: auth — container name inside the pod. Used in kubectl logs auth-pod-xxx -c auth and kubectl exec.

# image — assembled from values as saas-auth:v1. In Jenkins CI/CD, tag gets replaced with the Git commit SHA automatically on every build. So production image becomes saas-auth:abc1234 — fully traceable to the exact commit that built it.

# imagePullPolicy: IfNotPresent — use local image if it exists. Critical for local development — without this Kubernetes tries to pull from DockerHub and fails because we never pushed the image there.

# yaml
#           ports:
#             - name: http
#               containerPort: 8001
#               protocol: TCP

# Documents the port. containerPort does not actually open or restrict ports — that is NetworkPolicy's job. But naming it http lets the Service reference it by name (targetPort: http) instead of number. If port changes from 8001 to 9001, you only change it here — Service automatically follows the name.

# yaml
#           livenessProbe:
#             {{- toYaml .Values.livenessProbe | nindent 12 }}
#           readinessProbe:
#             {{- toYaml .Values.readinessProbe | nindent 12 }}

# toYaml converts the nested values block into a YAML string. nindent 12 indents it 12 spaces — matching the depth inside containers. This is the cleanest way to inject complex nested structures from values into templates.

# Kubernetes uses these probes every few seconds. Liveness failure = restart pod. Readiness failure = remove from traffic but keep running.

# yaml
#           resources:
#             {{- toYaml .Values.resources | nindent 12 }}

# Same toYaml pattern. Injects CPU and memory limits from values. Without this Kubernetes has no guardrails — one runaway pod can consume the entire node and starve all other tenants. This single block is what makes resource isolation in multi-tenancy work.

# yaml
#           securityContext:
#             allowPrivilegeEscalation: false
#             readOnlyRootFilesystem: true
#             capabilities:
#               drop:
#                 - ALL

# Container-level security — stricter than pod-level.

# allowPrivilegeEscalation: false — the process cannot gain more privileges than it started with. Blocks sudo, setuid binaries, and privilege escalation attacks entirely.

# readOnlyRootFilesystem: true — container filesystem is completely read-only. Malicious code trying to write files, install tools, or create backdoors fails immediately. Your legitimate app only needs to write to explicitly mounted volumes — not the container filesystem.

# capabilities.drop: ALL — Linux kernel capabilities are special permissions beyond normal user permissions. NET_ADMIN lets you configure network interfaces. SYS_ADMIN lets you do almost anything. Dropping ALL of them leaves the process with only what a normal unprivileged process can do. This is the single most impactful container security setting — and most fresher projects never touch it.

# The overall picture:

# values.yaml          →    Helm fills placeholders    →    Kubernetes receives plain YAML
# replicaCount: 1           replicas: {{ .Values... }}       replicas: 1
# image.tag: "v1"           image: "saas-auth:{{ ... }}"     image: "saas-auth:v1"
# tenant: tenant-a          tenant: {{ .Values.tenant }}     tenant: tenant-a

* NOTES.txt

What is this file?
A plain text file with Helm template syntax. It is not a Kubernetes resource — Kubernetes never sees it. It is purely a message printed to your terminal immediately after helm install or helm upgrade completes successfully.

Why do we need it?
When you or a teammate deploys this chart, the terminal shows this message automatically. It gives instant confirmation of what was deployed and the exact commands needed to verify it. In a team or production environment, this saves time — nobody needs to remember or look up how to access a newly deployed service.

How does it work?
After Helm finishes creating all Kubernetes resources, it reads NOTES.txt, renders any {{ }} template expressions in it, and prints the result to the terminal. It has access to the same .Values, .Release, and .Chart objects as other templates.

Line by Line:

Auth Service has been deployed successfully!

Plain text. No template syntax. Printed exactly as written. Gives immediate visual confirmation the deployment worked.

Release:   {{ .Release.Name }}
Namespace: {{ .Values.namespace }}
Tenant:    {{ .Values.tenant }}
Image:     {{ .Values.image.repository }}:{{ .Values.image.tag }}

.Release.Name — the name you gave the release at install time. If you ran helm install staging-auth ./helm/auth, this prints staging-auth.

.Values.namespace — which namespace it deployed into. Confirms isolation is correct.

.Values.tenant — confirms which tenant this belongs to.

.Values.image.repository and .Values.image.tag — confirms exactly which Docker image is running. Critical for debugging — if something is wrong you immediately know which image version to investigate.

kubectl port-forward svc/{{ include "auth.fullname" . }} 8001:{{ .Values.service.port }} -n {{ .Values.namespace }}

Port-forward is how you access a ClusterIP service locally without an Ingress. It creates a tunnel from your local machine into the cluster.

svc/ — target is a Service, not a pod directly. Service load-balances across pods.

8001:8001 — local port 8001 maps to Service port 8001. Left side is your machine, right side is the cluster.

-n {{ .Values.namespace }} — specifies the namespace. Without this kubectl defaults to default namespace and cannot find the service.

This command is printed dynamically with the actual release name and namespace — so it is always copy-paste ready with no manual substitution needed.

* service.yaml

# What is this file?
# A Service is a stable network endpoint for your pods. Pods die and restart constantly with new IP addresses. The Service sits in front of them with a fixed name and IP — other services always call the Service, never the pod directly.

# Why do we need it?
# Without a Service, the API service would need to know the exact IP of the auth pod to call it. That IP changes every restart. With a Service, API always calls http://auth-service:8001 — that name never changes regardless of how many times the pod restarts or reschedules.

# How does it work?
# Kubernetes runs a built-in DNS server. When you create a Service named auth in namespace tenant-a, Kubernetes automatically creates a DNS entry: auth.tenant-a.svc.cluster.local. Any pod in the cluster can resolve this name to the Service IP. The Service then load-balances across all healthy pods matching its selector.

# Block by Block:

# yaml
# apiVersion: v1
# kind: Service

# v1 is the core Kubernetes API — oldest and most stable. Services, Pods, and ConfigMaps all use v1. Unlike Deployments which use apps/v1, Services are so fundamental they live in the root API group.

# yaml
# metadata:
#   name: {{ include "auth.fullname" . }}
#   namespace: {{ .Values.namespace }}

# name — this becomes the DNS name inside the cluster. If fullname resolves to staging-auth, then other services call http://staging-auth:8001. The name is the address.

# namespace — Service must be in the same namespace as the pods it serves. Cross-namespace service calls are possible but require full DNS names. Keeping them in the same namespace is simpler and more secure.

# yaml
# spec:
#   type: {{ .Values.service.type }}

# ClusterIP from values. Three types and when to use each:

# ClusterIP    → internal only, no external access
#                use for: auth, api, database — services talking to each other

# NodePort     → opens a port on every node (30000-32767 range)
#                use for: local testing only, never production

# LoadBalancer → creates a cloud load balancer (AWS ALB/NLB)
#                use for: public-facing services in production
#                costs money — each LoadBalancer = one cloud LB

# For our architecture: auth and api are ClusterIP. Only Ingress needs external access — it handles all external traffic and routes internally to ClusterIP services.

# yaml
#   selector:
#     {{- include "auth.selectorLabels" . | nindent 4 }}

# This is how the Service finds its pods. It constantly watches for pods with these labels and routes traffic to them. Add a new pod with matching labels → Service automatically includes it. Remove a pod → Service stops routing to it. This is Kubernetes service discovery — no manual IP management, ever.

# The selector labels are:

# app.kubernetes.io/name: auth
# app.kubernetes.io/instance: <release-name>

# Both the Service selector and pod labels come from the same auth.selectorLabels helper — guaranteed to always match.

# yaml
#   ports:
#     - port: {{ .Values.service.port }}
#       targetPort: http
#       protocol: TCP
#       name: http

# port — what callers use. API service calls http://auth-service:8001. This is the Service port.

# targetPort: http — which port on the pod to forward traffic to. http references the named port http in deployment.yaml (containerPort: 8001, name: http). Using names instead of numbers means if the port changes, you change it once in deployment.yaml and Service follows automatically.

# protocol: TCP — HTTP runs over TCP. Other options: UDP for DNS/gaming, SCTP for telecom. Almost always TCP.

# name: http — names this port on the Service itself. Ingress and other resources can reference it by name.

# The full traffic flow:

# External request
#       ↓
#    Ingress          ← routes /auth/* to auth Service
#       ↓
#   Service (auth)    ← stable DNS name, load balances across pods
#       ↓
#    Pod 1            ← actual container running your FastAPI app
#    Pod 2            ← Kubernetes picks one based on load
#    Pod 3

* ingress.yaml

#                   What is this file?
# Ingress is the entry point for traffic coming from outside the Kubernetes cluster into your services. Think of it as the front door of your entire platform. Everything outside — browsers, mobile apps, external APIs — hits the Ingress first.

# Why do we need it?
# Services with ClusterIP are invisible to the outside world. They only exist inside the cluster. Ingress solves this — it sits at the edge, receives external traffic, and routes it to the correct internal Service based on the URL path or hostname. One Ingress can route to multiple services simultaneously.

# How does it work?
# Ingress itself is just a set of routing rules written in YAML. It needs an Ingress Controller to actually execute those rules. The controller is a running pod (usually NGINX) that reads your Ingress rules and configures itself accordingly. When traffic hits the controller pod, it checks the rules and forwards to the right Service.

# Browser → http://your-domain.com/auth/login
#                ↓
#         Ingress Controller (NGINX pod)
#                ↓ matches path /auth
#         auth Service (ClusterIP)
#                ↓
#         auth Pod

# Line by Line:

# yaml
# apiVersion: networking.k8s.io/v1
# kind: Ingress

# Ingress lives in the networking.k8s.io API group — not core v1. Networking resources like Ingress and NetworkPolicy are grouped separately from core resources because they are more complex and were added later.

# yaml
# metadata:
#   name: {{ include "auth.fullname" . }}
#   namespace: {{ .Values.namespace }}

# Same pattern as every other resource. Name generated from release name. Namespace isolates this Ingress to the tenant's namespace — Ingress rules in tenant-a namespace only affect traffic routed to tenant-a services.

# yaml
#   annotations:
#     nginx.ingress.kubernetes.io/rewrite-target: /

# Annotations pass controller-specific configuration that does not fit in standard Kubernetes spec. This one tells the NGINX Ingress Controller to rewrite the URL before forwarding.

# Without rewrite:

# Request:  /auth/health
# Forwarded to pod as: /auth/health   ← pod has no /auth route, returns 404

# With rewrite:

# Request:  /auth/health
# Forwarded to pod as: /health        ← pod has /health route, returns 200

# The /auth prefix is for the Ingress routing decision only — the pod itself does not know about it. This is standard practice when multiple services share one Ingress under different path prefixes.

# yaml
# spec:
#   rules:
#     - http:
#         paths:
#           - path: /auth
#             pathType: Prefix

# rules is a list — you can have multiple rules for different hosts or paths. We have one rule for HTTP traffic.

# path: /auth — any request starting with /auth matches this rule.

# pathType: Prefix — three options:

# Prefix          → /auth matches /auth, /auth/login, /auth/anything
# Exact           → /auth matches ONLY /auth, not /auth/login
# ImplementationSpecific → controller decides the matching logic

# We use Prefix because auth has multiple endpoints — /auth/login, /auth/register, /auth/verify. All need to be reachable.

# yaml
#             backend:
#               service:
#                 name: {{ include "auth.fullname" . }}
#                 port:
#                   number: {{ .Values.service.port }}

# Where to forward matching traffic. name is the Service name — must exactly match the Service created by service.yaml. port.number is the Service port — 8001 from values.

# This completes the chain:

# Ingress rule matches /auth → forwards to Service auth-fullname:8001 → Service routes to pod

* Values.yaml

#   replicaCount: 1 — how many pod copies to run. Change to 3 in production.

# image block — which Docker image to pull and how. repository + tag combines to saas-auth:v1. Jenkins will auto-replace tag with Git commit SHA in CI/CD.

# service block — ClusterIP means internal only. Port 8001 is what other services use to call auth.

# resources block — CPU and memory guardrails per pod. requests = guaranteed minimum for scheduling. limits = hard ceiling, pod gets killed if it exceeds memory limit. Critical for tenant isolation.

# livenessProbe — Kubernetes pings /health every 30s. Fails = restart pod.

# readinessProbe — Kubernetes pings /health every 10s. Fails = remove from traffic rotation but don't restart.

# namespace and tenant — our custom values for multi-tenancy. Templates use these to isolate resources per tenant.

# serviceAccount — creates a dedicated K8s identity for this pod instead of sharing the default one.

* helm\auth\templates\serviceaccount.yaml

# What is serviceaccount.yaml?
# A ServiceAccount is a Kubernetes identity for your pod. When a pod needs to talk to the Kubernetes API — to read secrets, list other pods, or access cluster resources — it authenticates using this identity.

# Why do we need it?
# By default every pod in a namespace shares one default ServiceAccount which has broad permissions. If one pod is compromised, the attacker inherits those broad permissions and can interact with the entire cluster. Creating a dedicated ServiceAccount per service lets you grant only the exact permissions that service actually needs — nothing more. This is the principle of least privilege applied at the Kubernetes level.

# How does it work?
# Kubernetes automatically mounts a token for the ServiceAccount into every pod at /var/run/secrets/kubernetes.io/serviceaccount/token. When the pod calls the Kubernetes API, it presents this token. Kubernetes checks what RBAC roles are bound to this ServiceAccount and allows or denies the request accordingly.

# The {{- if }} pattern:
# This file introduces a critical Helm concept — conditional rendering. If serviceAccount.create: false in values, this entire file produces nothing. No ServiceAccount is created. This lets operators reuse an existing ServiceAccount instead of creating a new one — useful in enterprise environments where ServiceAccounts are managed separately by a platform team.

# {{- if .Values.serviceAccount.create -}}

# Helm conditional. Reads serviceAccount.create from values.yaml — currently true. If someone sets it to false, everything between if and end is skipped entirely. The - on both sides strips whitespace so no blank lines appear in output when the block is skipped.

# yaml
# apiVersion: v1
# kind: ServiceAccount

# ServiceAccount lives in the core v1 API group — same as Services and Pods. Most fundamental Kubernetes resources use v1.

# yaml
# metadata:
#   name: {{ include "auth.serviceAccountName" . }}

# Uses the auth.serviceAccountName helper from _helpers.tpl. That helper checks — if serviceAccount.name is set in values, use that name. If empty, auto-generate from the release name. This gives operators flexibility to either let Helm name it or bring their own.

# yaml
#   namespace: {{ .Values.namespace }}

# ServiceAccount must be in the same namespace as the pod using it. A pod in tenant-a namespace cannot use a ServiceAccount from tenant-b namespace. This enforces tenant isolation at the identity level.

# yaml
#   labels:
#     {{- include "auth.labels" . | nindent 4 }}

# Same standard labels as every other resource. Includes tenant: {{ .Values.tenant }} — so you can query all resources belonging to a specific tenant with one label selector: kubectl get all -l tenant=tenant-a.

# yaml
# {{- end }}

# Closes the if block. Everything between if and end is conditionally rendered.