import os
import json
from typing import Optional
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
CORS(app)

# ---- DB CONFIG: Postgres if DATABASE_URL exists, else local SQLite ----
db_url = os.environ.get("DATABASE_URL", "sqlite:///orders.db")

# Normalize to SQLAlchemy's psycopg2 driver (v2)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url


# ---- MODEL ----
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    mode = db.Column(db.String(10))   # 'desk' (or future modes)
    name = db.Column(db.String(100))
    emp_code = db.Column(db.String(20))
    room_no = db.Column(db.String(50))  # includes 'Kitchen'
    order_json = db.Column(db.Text)     # full order as JSON (qty, sugar toggle etc.)
    delivered = db.Column(db.Boolean, default=False, nullable=False)


with app.app_context():
    db.create_all()


# ---- HELPERS ----
def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """
    Accepts 'YYYY-MM-DD' or ISO 'YYYY-MM-DDTHH:MM:SS[.fff][Z]'.
    Returns None if value is falsy or malformed.
    """
    if not value:
        return None
    try:
        if len(value) == 10:  # date only
            return datetime.fromisoformat(value)
        value = value.rstrip("Z")
        return datetime.fromisoformat(value)
    except Exception:
        return None


# ---- ROUTES ----
@app.route("/", methods=["GET"])
def health():
    return {"status": "ok"}, 200


# 1) Store a new order
@app.route("/store_order", methods=["POST"])
def store_order():
    data = request.get_json(silent=True) or {}
    order_payload = data.get("order", [])
    order_row = Order(
        mode=data.get("mode", "desk"),
        name=data.get("name"),
        emp_code=data.get("emp_code"),
        room_no=data.get("room_no"),
        order_json=json.dumps(order_payload, ensure_ascii=False),
    )
    db.session.add(order_row)
    db.session.commit()
    return jsonify({"message": "Order stored successfully", "id": order_row.id}), 200


# 2) Get recent undelivered orders
@app.route("/get_recent_orders", methods=["GET"])
def get_recent_orders():
    orders = (
        Order.query.filter_by(delivered=False)
        .order_by(Order.timestamp.desc())
        .limit(20)
        .all()
    )
    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "timestamp": o.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": o.mode,
            "name": o.name,
            "emp_code": o.emp_code,
            "room_no": o.room_no,
            "order": json.loads(o.order_json or "[]"),
        })
    return jsonify(result), 200


# 3) Mark as delivered
@app.route("/mark_delivered", methods=["POST"])
def mark_delivered():
    data = request.get_json(silent=True) or {}
    order_id = data.get("id")
    if not order_id:
        return jsonify({"error": "Missing 'id'"}), 400
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    order.delivered = True
    db.session.commit()
    return jsonify({"message": "Order marked as delivered"}), 200


# 4) Get all orders (optional date filters)
@app.route("/all_orders", methods=["GET"])
def all_orders():
    start_str = request.args.get("start")   # e.g. 2025-08-01
    end_str = request.args.get("end")       # e.g. 2025-08-08

    start_dt = _parse_iso_datetime(start_str)
    end_dt = _parse_iso_datetime(end_str)

    query = Order.query
    if start_dt:
        query = query.filter(Order.timestamp >= start_dt)
    if end_dt:
        if end_str and len(end_str) == 10:
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        query = query.filter(Order.timestamp <= end_dt)

    orders = query.order_by(Order.timestamp.desc()).all()
    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "timestamp": o.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": o.mode,
            "name": o.name,
            "emp_code": o.emp_code,
            "room_no": o.room_no,
            "delivered": o.delivered,
            "order": json.loads(o.order_json or "[]"),
        })
    return jsonify(result), 200


# ---- ENTRYPOINT ----
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
