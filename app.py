from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "PVR Watchlist Backend running", 200

@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "Service is healthy"}), 200

@app.route("/api/watch", methods=["POST"])
def add_watch():
    return jsonify({"status": "started", "message": "Watch added (placeholder)"}), 200

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
