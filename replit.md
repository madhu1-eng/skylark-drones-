# Skylark Drones Mission Agent

## Overview
A Python-based AI agent that automates drone mission assignment by reading from Google Sheets. It matches available pilots and drones to missions based on skills, certifications, weather resistance, budget, and location.

## Project Architecture
- `agent.py` - Main script that connects to Google Sheets and runs mission assignment logic
- `credentials.json` - Google Service Account credentials for Sheets API access

## Dependencies
- Python 3.11
- gspread - Google Sheets API client
- google-auth - Google authentication library

## How It Works
1. Connects to a Google Sheet named "missions" with three worksheets: pilot_roster, drone_fleet, missions
2. Iterates through missions and finds available pilots/drones
3. Checks skills, certifications, weather resistance, budget, and location
4. Handles urgent mission reassignment
5. Updates sheet status for assigned pilots and drones

## Running
Run `python agent.py` to execute the mission assignment agent.
