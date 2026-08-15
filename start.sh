#!/bin/bash
# All browser installations (playwright, camoufox) are handled at Docker build time.
# This script only starts the bot.
set -e
exec python Bot.py

