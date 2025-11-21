#!/bin/bash
# Test script for Docker integration tests
# Builds and tests the Dockerized service

set -e

echo "🐳 Building Docker image..."
docker-compose build

echo "🚀 Starting service..."
docker-compose up -d

echo "⏳ Waiting for service to be ready..."
sleep 10

echo "🧪 Running integration tests..."
RUN_DOCKER_TESTS=true uv run pytest tests/test_docker_integration.py -v

echo "🛑 Stopping service..."
docker-compose down

echo "✅ Docker integration tests complete!"
