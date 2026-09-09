"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Dashboard - Central Portal (Port 5000)
"""
from flask import Flask, render_template
import argparse

app = Flask(__name__, template_folder="templates")
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.route("/")
def index():
    return render_template("dashboard.html")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    print(f"\n  NWIS-Sentinel Dashboard  ->  http://localhost:{args.port}\n")
    app.run(host="0.0.0.0", port=args.port, debug=False)
