# Thin wrappers; Windows users can run the PowerShell scripts directly.
PS = powershell -NoProfile -ExecutionPolicy Bypass -File

.PHONY: setup backend frontend check up down docker-smoke seed-upp100

setup:
	$(PS) scripts/dev.ps1 setup

backend:
	$(PS) scripts/dev.ps1 backend

frontend:
	$(PS) scripts/dev.ps1 frontend

check:
	$(PS) scripts/check.ps1

up:
	docker compose up --build -d

down:
	docker compose down

docker-smoke:
	$(PS) scripts/docker-smoke.ps1

seed-upp100:
	cd backend && uv run python -c "from app.infrastructure.demo.upp100 import write_upp100_seed_file; print(write_upp100_seed_file())"
