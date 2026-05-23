"""
============================================================
GATEKEEPER AI — Python Agent Server 
============================================================
"""

import json
import os
import re
import datetime
import logging
import threading
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# ============================================================
# ─── CONFIG ─────────────────────────────────────────────────
# ============================================================

LM_STUDIO_URL  = "http://localhost:1234/v1"     # LM Studio local API endpoint
LM_MODEL       = "qwen/qwen3-4b-2507"           # Local model name loaded in LM Studio
# Telegram bot credentials
TELEGRAM_TOKEN   = "Your_Token"
TELEGRAM_CHAT_ID = "TChat_ID"
# JSON file used to store schedule
SCHEDULE_FILE = "schedule.json"

# ============================================================
# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("gatekeeper")       # Create logger instance

app = Flask(__name__)       # Create Flask application
lm_client = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")     # OpenAI-compatible client connected to LM Studio
RESEARCH_MODE_ACTIVE = False            # Manual do-not-disturb mode flag

# ============================================================
# ─── SCHEDULE ───────────────────────────────────────────────
# ============================================================
# Default weekly schedule if no JSON file exists
DEFAULT_SCHEDULE = [
    {"day": "Monday",    "start": "10:30", "end": "14:00", "label": "At the School"},
    {"day": "Tuesday",   "start": "07:00", "end": "10:00", "label": "Online Class - Control Systems"},
    {"day": "Tuesday",   "start": "17:30", "end": "20:30", "label": "Online Class - Operating Systems"},
    {"day": "Wednesday", "start": "07:00", "end": "10:00", "label": "Online Class - Operating Systems"},
    {"day": "Wednesday", "start": "10:30", "end": "13:00", "label": "At the School"},
    {"day": "Thursday",  "start": "18:00", "end": "21:00", "label": "Online Class - Software Design"},
    {"day": "Friday",    "start": "10:30", "end": "16:30", "label": "At the School"},
    {"day": "Friday",    "start": "17:00", "end": "20:00", "label": "Online Class - Microprocessors"},
    {"day": "Saturday",  "start": "07:00", "end": "16:00", "label": "At the School"},
]
# Load schedule from JSON file
def load_schedule() -> list:
    if os.path.exists(SCHEDULE_FILE):           # Check if schedule file exists
        try:
            with open(SCHEDULE_FILE, "r") as f:     # Open and parse JSON schedule
                data = json.load(f)
                log.info(f"Loaded {len(data)} events from {SCHEDULE_FILE}")     # Log successful load
                return data
        except Exception as e:
            log.warning(f"Could not load schedule file: {e}. Using defaults.")      # Fallback to default schedule if loading fails
    return DEFAULT_SCHEDULE.copy()      # Return default schedule if file does not exist
# Save schedule to JSON file
def save_schedule(schedule: list):
    try:
        with open(SCHEDULE_FILE, "w") as f:         # Write formatted JSON schedule
            json.dump(schedule, f, indent=2)
        log.info(f"Schedule saved ({len(schedule)} events)")        # Log save success
    except Exception as e:
        log.error(f"Could not save schedule: {e}")          # Log save error

WEEKLY_SCHEDULE = load_schedule()       # Global schedule loaded at startup

# ============================================================
# ─── TIME HELPERS ───────────────────────────────────────────
# ============================================================

def get_today_name() -> str:        # Get current weekday name
    return datetime.datetime.now().strftime("%A")   # e.g. "Tuesday"

def get_tomorrow_name() -> str:     # Get tomorrow's weekday name
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    return tomorrow.strftime("%A")

def get_current_time_str() -> str:      # Get current time in HH:MM format
    return datetime.datetime.now().strftime("%H:%M")

def parse_time_str(raw: str) -> str:        # Convert natural time text into HH:MM 24-hour format
    """
    Convert a natural time string to HH:MM 24-hour format.
    Handles: '1pm', '13:00', '1:30pm', '13', '1 pm', etc.
    Returns None if can't parse.
    """
    if not raw:     # Reject empty input
        return None
    raw = raw.strip().lower().replace(" ", "")          # Normalize string

    # Already HH:MM
    m = re.match(r'^(\d{1,2}):(\d{2})$', raw)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        return f"{h:02d}:{mn:02d}"

    # 12-hour with am/pm  e.g. 1pm, 1:30pm, 13pm (treat as 13:00)
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?(am|pm)$', raw)
    if m:
        h  = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        period = m.group(3)
        if period == "pm" and h != 12:      # Convert PM to 24-hour
            h += 12
        if period == "am" and h == 12:      # Convert midnight
            h = 0
        return f"{h:02d}:{mn:02d}"

    # Plain hour number e.g. "13" or "9"
    m = re.match(r'^(\d{1,2})$', raw)
    if m:
        h = int(m.group(1))
        return f"{h:02d}:00"

    return None
# Resolve natural language day into weekday
def resolve_day(raw: str) -> str:
    """
    Convert 'today', 'tomorrow', or a day name to a proper day name.
    """
    if not raw:     # Default to today if empty
        return get_today_name()
    raw = raw.strip().lower()
    if raw in ["today", "now"]:     # Handle today keywords
        return get_today_name()
    if raw == "tomorrow":           # Handle tomorrow keyword
        return get_tomorrow_name()
    # Capitalize properly
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    for d in days:
        if d.lower() == raw or d.lower().startswith(raw[:3]):
            return d
    return raw.capitalize()

# ============================================================
# ─── TELEGRAM ───────────────────────────────────────────────
# ============================================================
# Send Telegram message
def send_telegram(message: str):
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":         # Skip if token not configured
        log.warning("Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"       # Telegram Bot API endpoint
    try:
        resp = requests.post(url, json={        # Send POST request
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=5)
        if resp.status_code == 200:     # Check response
            log.info("Telegram notification sent.")
        else:
            log.warning(f"Telegram error: {resp.text}")
    except Exception as e:
        log.warning(f"Telegram failed: {e}")
# Notify user when door event occurs
def notify_door_event(lcd_message: str):
    now = datetime.datetime.now().strftime("%I:%M %p")      # Current readable time
    text = (            # Build Telegram message
        f"🚪 *Someone is at your door!*\n"
        f"🕐 Time: {now}\n"
        f"📟 LCD Message:\n`{lcd_message}`"
    )
    threading.Thread(target=send_telegram, args=(text,), daemon=True).start()       # Send asynchronously

# ============================================================
# ─── DOOR AGENT TOOLS ───────────────────────────────────────
# ============================================================
# Return current time details
def get_current_time() -> dict:
    now = datetime.datetime.now()
    return {
        "day_of_week": now.strftime("%A"),
        "time_24h":    now.strftime("%H:%M"),
        "time_12h":    now.strftime("%I:%M %p"),
        "date":        now.strftime("%Y-%m-%d"),
    }
# Check active and upcoming schedule events
def check_calendar(day_of_week: str, current_time: str) -> dict:
    def to_minutes(t: str) -> int:          # Convert HH:MM into total minutes
        h, m = map(int, t.split(":"))
        return h * 60 + m

    now_min = to_minutes(current_time)
    active_events, upcoming_events = [], []

    for event in WEEKLY_SCHEDULE:       # Iterate through weekly schedule
        if event["day"].lower() != day_of_week.lower():
            continue
        s = to_minutes(event["start"])
        e = to_minutes(event["end"])
        if s <= now_min < e:
            active_events.append({"label": event["label"], "ends_at": event["end"], "status": "active"})
        elif s > now_min:
            upcoming_events.append({"label": event["label"], "starts_at": event["start"], "status": "upcoming"})
    # Sort by start time
    upcoming_events.sort(key=lambda x: x["starts_at"])
    return {
        "active_events":     active_events,
        "next_event":        upcoming_events[0] if upcoming_events else None,
        "is_currently_busy": len(active_events) > 0
    }
# Check manual DND mode
def check_research_mode() -> dict:
    return {
        "research_mode_active": RESEARCH_MODE_ACTIVE,
        "reason": "Manual DND" if RESEARCH_MODE_ACTIVE else "No override"
    }
# Tool schemas exposed to LM Studio
TOOLS = [
    {"type": "function", "function": {
        "name": "get_current_time",
        "description": "Returns the current local time and day.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "check_calendar",
        "description": "Checks the user's schedule for a given day and time.",
        "parameters": {
            "type": "object",
            "properties": {
                "day_of_week":  {"type": "string"},
                "current_time": {"type": "string", "description": "HH:MM 24-hour"}
            },
            "required": ["day_of_week", "current_time"]
        }
    }},
    {"type": "function", "function": {
        "name": "check_research_mode",
        "description": "Checks if do-not-disturb mode is on.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }}
]
# Execute AI tool call
def dispatch_tool(name, args):
    log.info(f"  Tool: {name}({args})")         # Log tool usage
    if name == "get_current_time":      result = get_current_time()
    elif name == "check_calendar":      result = check_calendar(args.get("day_of_week",""), args.get("current_time",""))
    elif name == "check_research_mode": result = check_research_mode()
    else:                               result = {"error": f"Unknown tool: {name}"}
    log.info(f"  Result: {result}")
    return json.dumps(result)
# Prompt for LCD assistant behavior
DOOR_SYSTEM_PROMPT = """You are Gatekeeper, an AI assistant managing a smart door notification system.

When someone is detected at the door, check the user's schedule and return a SHORT, FRIENDLY message for a 16x2 LCD screen.

Rules:
- Maximum 32 characters total (2 lines x 16 chars)
- Line 1: status summary (16 chars max)
- Line 2: helpful detail (16 chars max)
- Be warm and informative
- Do NOT include line break characters

Good examples:
- "In online class. Back at 10:00 AM"
- "Busy at school. Back at 2:00 PM"
- "Free right now! Please knock :)"
- "No class today! Come on in :)"

Always call get_current_time first, then check_calendar."""

def run_door_agent() -> str:
    messages = [
        {"role": "system", "content": DOOR_SYSTEM_PROMPT},
        {"role": "user",   "content": "Someone is at the door. What should be shown on the LCD?"}
    ]
    for step in range(6):
        response = lm_client.chat.completions.create(
            model=LM_MODEL, messages=messages,
            tools=TOOLS, tool_choice="auto",
            temperature=0.3, max_tokens=300
        )
        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        messages.append(msg.model_dump(exclude_unset=False))

        if finish_reason == "tool_calls" and msg.tool_calls:
            for tc in msg.tool_calls:
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": dispatch_tool(tc.function.name, json.loads(tc.function.arguments or "{}"))
                })
        elif finish_reason == "stop":
            final = msg.content.strip() if msg.content else "Come back later"
            log.info(f"LCD message: '{final}'")
            return final
    return "Come back later"

# ============================================================
# ─── SCHEDULE CHAT ──────────────────────────────────────────
# ============================================================

def format_schedule_for_prompt() -> str:
    if not WEEKLY_SCHEDULE:
        return "No events scheduled."
    days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    lines = []
    for day in days_order:
        events = [e for e in WEEKLY_SCHEDULE if e["day"] == day]
        if events:
            lines.append(f"\n{day}:")
            for e in sorted(events, key=lambda x: x["start"]):
                lines.append(f"  {e['start']}–{e['end']}  {e['label']}")
    return "\n".join(lines)

def apply_action(action: dict) -> str:
    """Apply a schedule change and save to file."""
    global WEEKLY_SCHEDULE
    act = action.get("action", "").lower()

    if act == "add":
        day   = resolve_day(action.get("day", ""))
        start = parse_time_str(action.get("start", "")) or get_current_time_str()
        end   = parse_time_str(action.get("end", ""))
        label = action.get("label", "Event")
        if not end:
            return "Could not parse end time."
        new_event = {"day": day, "start": start, "end": end, "label": label}
        WEEKLY_SCHEDULE.append(new_event)
        save_schedule(WEEKLY_SCHEDULE)
        return f"✅ Added: {label} on {day} {start}–{end}"

    elif act == "remove":
        day   = resolve_day(action.get("day", ""))
        start = parse_time_str(action.get("start", ""))
        label = action.get("label", "")
        before = len(WEEKLY_SCHEDULE)
        WEEKLY_SCHEDULE = [
            e for e in WEEKLY_SCHEDULE
            if not (
                e["day"].lower() == day.lower() and
                (not start or e["start"] == start) and
                (not label or label.lower() in e["label"].lower())
            )
        ]
        removed = before - len(WEEKLY_SCHEDULE)
        save_schedule(WEEKLY_SCHEDULE)
        return f"✅ Removed {removed} event(s) from {day}."

    elif act == "clear_day":
        day = resolve_day(action.get("day", ""))
        WEEKLY_SCHEDULE = [e for e in WEEKLY_SCHEDULE if e["day"].lower() != day.lower()]
        save_schedule(WEEKLY_SCHEDULE)
        return f"✅ Cleared all events for {day}."

    elif act == "update":
        # Remove old event, add new one
        day     = resolve_day(action.get("day", ""))
        old_label = action.get("old_label", "")
        old_start = parse_time_str(action.get("old_start", ""))
        new_start = parse_time_str(action.get("new_start", "")) or get_current_time_str()
        new_end   = parse_time_str(action.get("new_end", ""))
        new_label = action.get("new_label", old_label)

        if not new_end:
            return "Could not parse end time."

        before = len(WEEKLY_SCHEDULE)
        WEEKLY_SCHEDULE = [
            e for e in WEEKLY_SCHEDULE
            if not (
                e["day"].lower() == day.lower() and
                (not old_label or old_label.lower() in e["label"].lower()) and
                (not old_start or e["start"] == old_start)
            )
        ]
        removed = before - len(WEEKLY_SCHEDULE)
        WEEKLY_SCHEDULE.append({"day": day, "start": new_start, "end": new_end, "label": new_label})
        save_schedule(WEEKLY_SCHEDULE)
        return f"✅ Updated {day}: removed {removed} old event(s), added '{new_label}' {new_start}–{new_end}."

    return "Unknown action."

def parse_action_from_response(response_text: str):
    """
    Extract <ACTION>...</ACTION> block from AI response.
    Tries strict JSON parse, then lenient cleanup.
    """
    if "<ACTION>" not in response_text or "</ACTION>" not in response_text:
        return None
    try:
        start = response_text.index("<ACTION>") + len("<ACTION>")
        end   = response_text.index("</ACTION>")
        raw   = response_text[start:end].strip()
        # Remove any markdown fences the model might add
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        log.warning(f"Could not parse <ACTION> block: {e}")
        return None

# ── System prompt for schedule chat ──────────────────────────
SCHEDULE_SYSTEM_PROMPT = """You are a friendly schedule manager for Gatekeeper AI.

Today is {today}. Current time is {current_time}.

The user's current schedule:
{schedule}

You help the user add, remove, update, or view their weekly schedule.

IMPORTANT — When the user wants to change the schedule, you MUST always end your reply with an <ACTION> block.
The action block must be valid JSON. Choose one of these action types:

ADD an event:
<ACTION>
{{"action": "add", "day": "Monday", "start": "13:00", "end": "15:00", "label": "Going outside"}}
</ACTION>

REMOVE an event:
<ACTION>
{{"action": "remove", "day": "Monday", "start": "13:00", "label": "Going outside"}}
</ACTION>

UPDATE/MODIFY an existing event (use this when user says "modify", "update", "change", "move"):
<ACTION>
{{"action": "update", "day": "Monday", "old_label": "Valorant", "new_start": "14:00", "new_end": "16:00", "new_label": "Playing Valorant"}}
</ACTION>

CLEAR all events for a day:
<ACTION>
{{"action": "clear_day", "day": "Saturday"}}
</ACTION>

Rules for filling in the action:
- "today" means {today}
- "tomorrow" means {tomorrow}
- "this time" or "now" means {current_time}
- Times like "1pm", "3:30pm", "15:00" are all valid for start/end
- "until 4pm" with no start time = use current time as start
- "from now until X" = start is current time
- Always include a descriptive label

After the action, confirm what you did in plain language. Be friendly."""

def run_schedule_chat():
    print("\n" + "="*55)
    print("  GATEKEEPER — Schedule Manager")
    print("  Talk to the AI to manage your schedule.")
    print("  Examples:")
    print("    'I will go outside from 1pm to 3pm today'")
    print("    'Modify my valorant session to end at 4pm'")
    print("    'Clear today and add: outside until 5pm'")
    print("    'Show my full schedule'")
    print("    'Remove Thursday software design class'")
    print("  Type 'exit' to quit.")
    print("="*55 + "\n")

    chat_history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Schedule chat closed.")
            break
        if not user_input:
            continue

        # Build fresh system prompt with current time/day each turn
        system = (SCHEDULE_SYSTEM_PROMPT
            .replace("{today}",        get_today_name())
            .replace("{tomorrow}",     get_tomorrow_name())
            .replace("{current_time}", get_current_time_str())
            .replace("{schedule}",     format_schedule_for_prompt())
        )

        messages = [{"role": "system", "content": system}] + chat_history + [{"role": "user", "content": user_input}]

        try:
            response = lm_client.chat.completions.create(
                model=LM_MODEL,
                messages=messages,
                temperature=0.3,    # lower = more consistent action output
                max_tokens=600
            )
            reply = response.choices[0].message.content.strip()

            # Try to extract and apply action
            action = parse_action_from_response(reply)
            if action:
                result = apply_action(action)
                display_reply = reply[:reply.index("<ACTION>")].strip()
                print(f"\nGatekeeper: {display_reply}")
                print(f"  [{result}]\n")
            else:
                print(f"\nGatekeeper: {reply}\n")

            # Keep last 10 turns of history
            chat_history.append({"role": "user",      "content": user_input})
            chat_history.append({"role": "assistant",  "content": reply})
            if len(chat_history) > 20:
                chat_history = chat_history[-20:]

        except Exception as e:
            print(f"\n[Error: {e}]\n")

# ============================================================
# ─── FLASK ENDPOINTS ────────────────────────────────────────
# ============================================================

@app.route("/check", methods=["POST"])
def check_door():
    log.info("=== Door event from ESP32 ===")
    try:
        lcd_message = run_door_agent()
        if len(lcd_message) > 64:
            lcd_message = lcd_message[:64]
        notify_door_event(lcd_message)
        return jsonify({"status": "ok", "message": lcd_message})
    except Exception as e:
        log.error(f"Agent error: {e}")
        return jsonify({"status": "error", "message": "Agent offline"}), 500

@app.route("/health", methods=["GET"])
def health():
    now = get_current_time()
    cal = check_calendar(now["day_of_week"], now["time_24h"])
    return jsonify({"status": "ok", "time": now, "calendar": cal, "schedule_count": len(WEEKLY_SCHEDULE)})

@app.route("/schedule", methods=["GET"])
def get_schedule_route():
    return jsonify({"schedule": WEEKLY_SCHEDULE})

@app.route("/research-mode", methods=["POST"])
def toggle_research():
    global RESEARCH_MODE_ACTIVE
    data = request.get_json(silent=True) or {}
    RESEARCH_MODE_ACTIVE = bool(data.get("active", False))
    state = "ON" if RESEARCH_MODE_ACTIVE else "OFF"
    return jsonify({"research_mode": RESEARCH_MODE_ACTIVE, "message": f"Research mode is now {state}"})

# ============================================================
# ─── ENTRY POINT ────────────────────────────────────────────
# ============================================================

if __name__ == "__main__":
    log.info("=" * 55)
    log.info("  GATEKEEPER AI Agent Server")
    log.info("  Flask  → http://0.0.0.0:5050")
    log.info("  LM Studio → http://localhost:1234/v1")
    log.info("=" * 55)

    try:
        models = lm_client.models.list()
        log.info(f"  Models: {[m.id for m in models.data]}")
    except Exception as e:
        log.warning(f"  LM Studio not reachable: {e}")

    if TELEGRAM_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN":
        log.info("  Telegram: ENABLED")
        send_telegram("✅ Gatekeeper AI is online and watching your door!")
    else:
        log.warning("  Telegram: NOT configured")

    flask_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5050, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    log.info("  Server running. Opening schedule chat...\n")

    run_schedule_chat()
    log.info("Shutting down.")
