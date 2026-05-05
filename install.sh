#!/usr/bin/env bash
set -e

SKILL_DIR="$HOME/.claude/skills/Mr_Deepseeker"

echo "Installing Mr_Deepseeker skill..."

# Copy skill files
mkdir -p "$SKILL_DIR"
cp -r "$(dirname "$0")/claude_skill/." "$SKILL_DIR/"

# Prompt for API key
read -rp "DeepSeek API key (get one free at platform.deepseek.com): " API_KEY
echo "DEEPSEEK_API_KEY=$API_KEY" > "$SKILL_DIR/.env"

echo ""
echo "Done. Restart Claude Code and Mr_Deepseeker is live."
