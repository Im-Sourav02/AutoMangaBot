#!/bin/bash
set -e

# If running inside Docker the browsers are pre-installed during the build stage.
# Only install them on bare-metal / development environments.

if ! playwright install chromium 2>/dev/null | grep -q "already installed"; then
    echo "Installing OS-level Playwright dependencies..."
    playwright install-deps

    echo "Downloading Playwright Chromium..."
    playwright install chromium
fi

if ! camoufox fetch --check 2>/dev/null; then
    echo "Downloading Camoufox browser..."
    camoufox fetch
fi

echo "Starting the bot..."
python Bot.py

