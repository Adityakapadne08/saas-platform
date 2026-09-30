# SaaS Platform — Full Command Reference
> Every command run during this project, organized by phase, in the order they were first used.

---

## 1. Environment Setup

```powershell
# Verify tools
docker --version
python --version
git --version
aws --version
terraform --version
helm version

# Python virtual environment
cd C:\Users\DELL\Downloads\saas-platform
python -m venv venv
venv\Scripts\Activate.ps1
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# Install Python packages
pip install fastapi uvicorn python-jose[cryptography] passlib[bcrypt]
pip install prometheus-fastapi-instrumentator
pip freeze > services\auth\requirements.txt
Copy-Item services\auth\requirements.txt services\api\requirements.txt
```

---

## 2. Git & GitHub

```powershell
# Identity (one-time)
git config --global user.email "youremail@gmail.com"
git config --global user.name "Your Name"
git config --global core.autocrlf input

# Repo init
git init
git add .gitignore
git commit -m "chore: initial project structure and gitignore"

# Remote setup
git remote add origin https://github.com/Adityakapadne08/saas-platform.git
git branch -M main
git push -u origin main

# Auth with PAT (used when password auth was rejected)
git remote set-url origin https://USERNAME:TOKEN@github.com/Adityakapadne08/saas-platform.git

# Everyday cycle (used dozens of times throughout)
git add <path>
git commit -m "type: message"
git push
git pull origin main
git status
git log --oneline -3
git diff <file>

# Tagging
git tag -a v1.0.0 -m "message"
git push origin main --tags
```

---

## 3. Auth & API Service — Local Run

```powershell
# Run locally
uvicorn services.auth.main:app --reload --port 8001
uvicorn services.api.main:app --reload --port 8002

# Test endpoints
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/metrics
```

---

## 4. Docker — Images

```powershell
# Build
docker build -t saas-auth:v1 services\auth
docker build -t saas-api:v1 services\api

# Run standalone
docker run -d --name auth-service -p 8001:8001 saas-auth:v1

# Inspect
docker ps
docker images
docker info

# Cleanup
docker stop auth-service
docker rm auth-service

# Test
curl http://localhost:8001/health
```

---

## 5. Docker Compose

```powershell
docker compose up -d
docker compose down
docker compose ps
docker compose logs auth
```

---

## 6. Kubernetes (Docker Desktop local cluster)

```powershell
kubectl get nodes
kubectl get pods -n default
kubectl get all -n default
kubectl get all -n default -l app.kubernetes.io/name=auth
kubectl get pod -n default -l app.kubernetes.io/name=api -o jsonpath="{.items[0].spec.containers[0].image}"

# Logs & debug
kubectl logs <pod-name> -n default
kubectl describe application auth-service -n argocd
kubectl rollout status deployment/api-service -n default

# Port forwarding
kubectl port-forward svc/auth-local 8001:8001 -n default
kubectl port-forward svc/auth-service 8011:8001 -n default
kubectl port-forward svc/api-service 8010:8002 -n default
kubectl port-forward svc/kube-stack-grafana -n monitoring 3000:80
kubectl port-forward svc/argocd-server -n argocd 8081:443
```

---

## 7. Helm

```powershell
# PATH fix (Windows-specific, one-time)
$env:PATH += ";C:\Users\DELL\AppData\Local\Microsoft\WinGet\Links"
[System.Environment]::SetEnvironmentVariable("PATH", $env:PATH, "User")

# Create charts
helm create helm\auth
helm create helm\api

# Validate before deploy
helm template auth-local ./helm/auth
helm template api-local ./helm/api
helm template auth-test ./helm/auth | Select-String "prometheus"

# Deploy / manage
helm install auth-local ./helm/auth
helm install api-local ./helm/api
helm uninstall auth-local
helm uninstall api-local
helm list -n monitoring

# Add repos (for monitoring stack)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

---

## 8. Terraform

```powershell
# Install
winget install Hashicorp.Terraform

# Init / plan / apply
cd terraform\envs\staging
terraform init
terraform init -reconfigure
terraform plan
terraform apply
terraform apply -auto-approve
terraform destroy   # (documented as required cleanup step)
```

---

## 9. AWS CLI

```powershell
# Configure
aws configure
aws sts get-caller-identity
aws sts get-caller-identity --no-cli-pager

# S3 backend bucket
aws s3api create-bucket --bucket saas-terraform-state-431056843151 --region ap-south-1 --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket saas-terraform-state-431056843151 --versioning-configuration Status=Enabled
aws s3 ls | findstr saas-terraform

# DynamoDB lock table
aws dynamodb create-table --table-name saas-terraform-locks --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region ap-south-1
aws dynamodb list-tables --region ap-south-1

# IAM check
aws iam list-attached-user-policies --user-name terraform-saas --no-cli-pager

# EKS addon lookup (debugging supported k8s versions)
aws eks describe-addon-versions --addon-name kube-proxy
aws eks describe-addon-versions --addon-name kube-proxy --kubernetes-version 1.28
```

---

## 10. Jenkins

```powershell
# Run Jenkins container
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 `
  -v jenkins_home:/var/jenkins_home `
  -v //var/run/docker.sock:/var/run/docker.sock `
  jenkins/jenkins:lts

# Initial admin password
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword

# Container lifecycle
docker start jenkins
docker restart jenkins
docker ps -a | findstr jenkins

# Fix: install Docker CLI inside Jenkins container
docker exec -u root jenkins bash -c "apt-get update && apt-get install -y docker.io"

# Fix: Docker socket permissions (recurring issue after restarts)
docker exec -u root jenkins bash -c "chmod 666 /var/run/docker.sock"

# Fix: outdated CA certificates
docker exec -u root jenkins bash -c "apt-get update && apt-get install -y ca-certificates && update-ca-certificates"

# Reset admin password (disable security temporarily)
docker exec jenkins sed -i 's/<useSecurity>true<\/useSecurity>/<useSecurity>false<\/useSecurity>/' /var/jenkins_home/config.xml
docker restart jenkins

# Shell into container (debugging)
docker exec -it jenkins bash
```

---

## 11. ArgoCD

```powershell
# Install
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl get pods -n argocd

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("PASTE_HERE"))

# Apply Application manifests
kubectl apply -f k8s\base\argocd-auth-app.yaml
kubectl apply -f k8s\base\argocd-api-app.yaml
kubectl get applications -n argocd

# Force manual sync (used repeatedly when auto-sync lagged)
'{"operation":{"initiatedBy":{"username":"admin"},"sync":{}}}' | Out-File -Encoding utf8 patch.json
kubectl patch app auth-service -n argocd --type merge --patch-file patch.json
kubectl patch app api-service -n argocd --type merge --patch-file patch.json

# Inspect sync state / history
kubectl describe application api-service -n argocd
kubectl describe application api-service -n argocd | Select-String -Pattern "Revision:|Images:"
```

---

## 12. Prometheus + Grafana (kube-prometheus-stack)

```powershell
kubectl create namespace monitoring
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring
kubectl get pods -n monitoring

# Grafana access
kubectl port-forward svc/kube-stack-grafana -n monitoring 3000:80
kubectl get secret kube-stack-grafana -n monitoring -o jsonpath="{.data.admin-password}"
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("PASTE_HERE"))
```

---

## 13. Verification / Troubleshooting Utilities Used Throughout

```powershell
# Search inside files
Select-String -Path jenkins\Jenkinsfile -Pattern "severity"
Select-String -Path services\api\requirements.txt -Pattern "jose"
Select-String -Path helm\api\values.yaml -Pattern "tag:"

# View file / directory contents
cat helm\api\values.yaml
cat services\auth\requirements.txt
tree jenkins /F
tree helm /F
tree terraform /F

# Rename / cleanup
Rename-Item terraform\envs\staging\output.tf terraform\envs\staging\outputs.tf
Remove-Item helm\auth\templates\httproute.yaml
Remove-Item -Recurse -Force venv

# Pagers (when output got stuck)
# press 'q' to exit AWS CLI / kubectl pager
```
