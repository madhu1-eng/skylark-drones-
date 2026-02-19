import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from flask import Flask, request, render_template_string
import threading
import os
import time

app = Flask(__name__)

# ---------------- SAFE GOOGLE CONNECTION ----------------
def connect_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(
        "credentials.json", scopes=scope
    )

    client = gspread.authorize(creds)
    sheet = client.open("missions")

    return (
        sheet.worksheet("pilot_roster"),
        sheet.worksheet("drone_fleet"),
        sheet.worksheet("missions"),
    )


# ---------------- HELPERS ----------------
def mission_days(m):
    start = datetime.fromisoformat(m["start_date"])
    end = datetime.fromisoformat(m["end_date"])
    return (end - start).days + 1


def detect_conflicts():
    try:
        pilot_ws, drone_ws, mission_ws = connect_sheets()
    except Exception as e:
        return [f"Sheets connection error: {e}"]

    conflicts = []

    pilots = pilot_ws.get_all_records()
    drones = drone_ws.get_all_records()
    missions = mission_ws.get_all_records()

    for d in drones:
        if d.get("status") == "Maintenance" and d.get("current_assignment"):
            conflicts.append(
                f"Drone {d['drone_id']} under maintenance but assigned."
            )

    for m in missions:
        for p in pilots:
            if p.get("current_assignment") == m.get("project_id"):
                days = mission_days(m)
                cost = days * p.get("daily_rate_inr", 0)
                if cost > m.get("mission_budget_inr", 0):
                    conflicts.append(
                        f"Budget overrun in mission {m['project_id']}"
                    )

    return conflicts


# ---------------- ASSIGNMENT ENGINE ----------------
def run_agent_cycle():
    try:
        pilot_ws, drone_ws, mission_ws = connect_sheets()
    except Exception as e:
        return [f"Sheets connection error: {e}"]

    logs = []

    pilots = pilot_ws.get_all_records()
    drones = drone_ws.get_all_records()
    missions = mission_ws.get_all_records()

    for m in missions:
        logs.append(f"Checking mission {m['project_id']}")

        pilot = None
        drone = None

        for p in pilots:
            if p.get("status") != "Available":
                continue
            if m.get("required_skills") not in p.get("skills", ""):
                continue
            if m.get("required_certs") not in p.get("certifications", ""):
                logs.append(f"Certification mismatch: {p['name']}")
                continue
            pilot = p
            break

        if not pilot and m.get("priority") == "Urgent":
            for p in pilots:
                if p.get("status") == "Assigned":
                    logs.append(f"🚨 Reassigning {p['name']}")
                    pilot = p
                    break

        for d in drones:
            if d.get("status") != "Available":
                continue

            if (
                m.get("weather_forecast") == "Rainy"
                and "Rain" not in d.get("weather_resistance", "")
            ):
                logs.append(f"Weather risk: {d['drone_id']}")
                continue

            drone = d
            break

        if not pilot:
            logs.append("No pilot available")
            continue

        if not drone:
            logs.append("No drone available")
            continue

        cost = mission_days(m) * pilot.get("daily_rate_inr", 0)

        if cost > m.get("mission_budget_inr", 0):
            logs.append("Budget exceeded")
            continue

        try:
            pilot_row = pilot_ws.findall(pilot["name"])[0].row
            drone_row = drone_ws.findall(drone["drone_id"])[0].row

            pilot_ws.update_cell(pilot_row, 6, "Assigned")
            pilot_ws.update_cell(pilot_row, 7, m["project_id"])

            drone_ws.update_cell(drone_row, 4, "Assigned")
            drone_ws.update_cell(drone_row, 7, m["project_id"])

            logs.append(f"Assigned {pilot['name']} & {drone['drone_id']}")
        except Exception as e:
            logs.append(f"Update failed: {e}")

    return logs


# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():
    conflicts = detect_conflicts()

    html = """
    <h1>🚁 Skylark Drones Operations Dashboard</h1>

    <h2>⚠ Conflict Alerts</h2>
    <pre>{{ conflicts }}</pre>

    <h2>Chat</h2>
    <form action="/chat" method="post">
        <input name="message" placeholder="Type command..." />
        <button type="submit">Send</button>
    </form>

    <br>
    <a href="/run">Run Assignment Now</a>
    """

    return render_template_string(html, conflicts=conflicts)


@app.route("/chat", methods=["POST"])
def chat():
    msg = request.form["message"].lower()

    if "run" in msg:
        logs = run_agent_cycle()
        return "<br>".join(logs)

    if "conflicts" in msg:
        return "<br>".join(detect_conflicts())

    return "Try: run assignment or conflicts"


@app.route("/run")
def run_manual():
    logs = run_agent_cycle()
    return "<br>".join(logs) + "<br><br><a href='/'>Back</a>"


# ---------------- START ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
