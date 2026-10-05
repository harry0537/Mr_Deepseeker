#!/usr/bin/env bash
set -e

SKILL_DIR="$HOME/.claude/skills/Mr_Deepseeker"
REPO="https://github.com/harry0537/Mr_Deepseeker.git"

echo "Installing Mr_Deepseeker skill..."

if [ -d "$SKILL_DIR/.git" ]; then
    git -C "$SKILL_DIR" pull --ff-only
else
    mkdir -p "$(dirname "$SKILL_DIR")"
    git clone "$REPO" "$SKILL_DIR"
fi

if [ ! -f "$SKILL_DIR/.env" ]; then
    cp "$SKILL_DIR/.env.example" "$SKILL_DIR/.env"
fi
chmod 600 "$SKILL_DIR/.env"

echo ""
echo "Done. Now open $SKILL_DIR/.env and replace paste-your-key-here"
echo "with your DeepSeek key (https://platform.deepseek.com/api_keys)."
echo "Then restart Claude Code."
