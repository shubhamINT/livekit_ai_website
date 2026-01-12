#!/bin/bash
set -e

echo "Starting deployment..."

echo "Pulling latest code..."
git pull origin master

echo "Building and starting services..."
# --wait ensures we wait for healthchecks to pass before exiting the command
# This effectively replaces the manual loop used previously
docker compose up -d --build --wait

echo "Cleaning up..."
# Prune stopped containers, networks, and dangling images
docker system prune -f

echo "Deployment completed successfully."