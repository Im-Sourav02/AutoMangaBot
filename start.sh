#!/bin/bash
echo "Installing Playwright browsers..."
playwright install chromium

echo "Installing Camoufox browser..."
camoufox fetch

echo "Starting the bot..."
python Bot.py
