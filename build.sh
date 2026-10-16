#!/bin/bash
# 🔨 Cross-compile CleanPhone agent pro Android
# Výsledek: statický binár, žádné závislosti, žádná appka

set -e
cd "$(dirname "$0")"

mkdir -p dist

echo "🔨 Building for Android (arm64) -> dist/agent-arm64"
GOOS=android GOARCH=arm64 CGO_ENABLED=0 \
  go build -trimpath -ldflags "-s -w" -o dist/agent-arm64 ./agent

echo "🔨 Building for Linux (local test) -> dist/agent-linux"
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 \
  go build -trimpath -ldflags "-s -w" -o dist/agent-linux ./agent

echo ""
echo "✅ Hotovo:"
ls -la dist/
echo ""
file dist/* 2>/dev/null || true
