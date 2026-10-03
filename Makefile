# Thin wrappers; Windows users can run the PowerShell scripts directly.
PS = powershell -NoProfile -ExecutionPolicy Bypass -File

.PHONY: setup backend frontend check up down

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
