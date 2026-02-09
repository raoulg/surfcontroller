# Makefile for Surf Controller Scheduler

IMAGE_NAME := raoulgrouls/surf-scheduler:latest
PLATFORM := linux/amd64

.PHONY: help build build-push deploy local-run clean

help:
	@echo "Surf Controller Management"
	@echo ""
	@echo "Usage:"
	@echo "  make scheduler-build       - Build the Docker image locally"
	@echo "  make scheduler-push        - Build and push the Docker image to Docker Hub ($(IMAGE_NAME))"
	@echo "  make deploy      - Run the full deployment script (build, push, and remote restart)"
	@echo "  make build-uv    - Build and publish the package to PyPI using UV"
	@echo "  make local-run   - Start the scheduler locally using docker-compose"
	@echo "  make remote-logs - View the scheduler logs on the remote server"
	@echo "  make clean       - Remove build artifacts"

scheduler-build:
	docker build -t $(IMAGE_NAME) -f scheduler/Dockerfile .

scheduler-push:
	docker buildx build --platform $(PLATFORM) -t $(IMAGE_NAME) -f scheduler/Dockerfile . --push

deploy:
	python3 scheduler/deploy.py

build-uv:
	uv build --wheel
	uv publish

local-run:
	cd scheduler && docker-compose up --build

remote-logs:
	@if [ -f scheduler/.env ]; then \
		HOST=$$(grep DEPLOY_HOST scheduler/.env | cut -d '=' -f2); \
		USER=$$(grep REMOTE_USER scheduler/.env | cut -d '=' -f2); \
		ssh $$USER@$$HOST "docker exec surf-scheduler cat /var/log/cron.log"; \
	else \
		echo "scheduler/.env not found"; \
	fi

clean:
	rm -rf dist/ build/ *.egg-info
