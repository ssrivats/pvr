"""
PVR Watchlist Backend – Simple Version (No Playwright)
"""

import json, logging, os, re, threading, time, uuid, requests
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
from twilio.rest import Client

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

TWILIO_SID   = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM  = os.environ.get("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")

REDIS_URL = os.environ.get("REDIS_URL", "")
_redis = None
_local_store = {}

if REDIS_URL:
    try:
        import redis as redis_lib
        _redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
        _redis.ping()
    except:
        pass

MAX_WATCHLIST_PER_PHONE = 10

def _save(watch_id, data):
    if _redis:
        _redis.set(f"watch:{watch_id}", json.dumps(data), ex=172800)
    else:
        _local_store[watch_id] = data

def _load(watch_id):
    if _redis:
        raw = _redis.get(f"watch:{watch_id}")
        return json.loads(raw) if raw else None
    return _local_store.get(watch_id)

def _log(watch_id, msg, kind="info"):
    item = _load(watch_id)
    if not item: return
    item.setdefault("logs", []).append({"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "kind": kind})
    _save(watch_id, item)
    log.info("[%s] %s", watch_id, msg)

def _slugify(name):
    s = name.lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s-]+', '-', s)
    return s.strip('-')

def _parse_seat_layout_api(data):
    try:
        categories = data.get("data", {}).get("categories") or data.get("categories", [])
        available = []
        for cat in categories:
            name = cat.get("name", "").lower()
            seats = int(cat.get("availableSeats") or 0)
            price = float(cat.get("price") or 0)
            if "elite" in name and seats > 0:
                available.append({"name": cat.get("name"), "price": price})
        if available:
            return {"found": True, "available": available}
    except:
        pass
    return {"found": False}

# Simple polling (placeholder - you can improve later)
def _poll_seats():
    # For now return false. We will add real logic after build succeeds
    return {"found": False}

def _send_alert(watch_id, movie_title, phone, found_seats):
    if not phone.startswith("+"):
        phone = f"+91{phone}"
    msg = f"🎬 *Back seats opened on PVR!*\n\n*{movie_title}*\n\n"
    for s in found_seats[:3]:
        msg += f"💺 {s['name']} ₹{int(s['price'])}\n\n"
    msg += "_PVR Watchlist_"

    if TWILIO_SID and TWILIO_TOKEN:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=msg, from_=TWILIO_FROM, to=f"whatsapp:{phone}")

def _run_monitor(watch_id):
    item = _load(watch_id)
    if not item: return

    event_code = item["eventCode"]
    phone = item["phone"]
    movie_title = item["movie"]

    item["status"] = "monitoring"
    _save(watch_id, item)

    while True:
        item = _load(watch_id)
        if item["status"] != "monitoring":
            break

        result = _poll_seats()

        if result.get("found"):
            _send_alert(watch_id, movie_title, phone, result.get("available", []))
            item["status"] = "alert_sent"
            _save(watch_id, item)
            break

        time.sleep(30)

@app.route("/api/watch", methods=["POST"])
def add_watch():
    data = request.json or {}
    phone = data.get("phone")
    event_code = data.get("eventCode")
    movie = data.get("movie")

    if not phone or not event_code or not movie:
        return jsonify({"error": "Missing fields"}), 400

    watch_id = str(uuid.uuid4())[:8]
    item = {
        "id": watch_id,
        "movie": movie,
        "eventCode": event_code,
        "phone": phone,
        "status": "starting",
        "added_at": datetime.now().isoformat(),
        "logs": []
    }
    _save(watch_id, item)

    threading.Thread(target=_run_monitor, args=(watch_id,), daemon=True).start()

    return jsonify({"watch_id": watch_id, "status": "started"})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
