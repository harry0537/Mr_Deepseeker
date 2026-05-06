#!/usr/bin/env bash
set -e

SKILL_DIR="$HOME/.claude/skills/Mr_Deepseeker"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing Mr_Deepseeker skill..."

# Copy skill files + Python module
mkdir -p "$SKILL_DIR"
cp -r "$REPO_DIR/claude_skill/." "$SKILL_DIR/"
cp -r "$REPO_DIR/mr_deepseeker" "$SKILL_DIR/"
cp -r "$REPO_DIR/scripts" "$SKILL_DIR/"
cp -r "$REPO_DIR/examples" "$SKILL_DIR/"

# Prompt for API key
read -rp "DeepSeek API key (get one free at platform.deepseek.com): " API_KEY
echo "DEEPSEEK_API_KEY=$API_KEY" > "$SKILL_DIR/.env"

echo ""
echo "Done. Restart Claude Code and Mr_Deepseeker is live."
