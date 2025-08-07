from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

# SQLite DB configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orders.db'
db = SQLAlchemy(app)

# Define the Order table
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    mode = db.Column(db.String(10))  # 'desk'
    name = db.Column(db.String(100))
    emp_code = db.Column(db.String(20))
    room_no = db.Column(db.String(50))  # includes 'Kitchen'
    order_json = db.Column(db.Text)  # Full order as JSON (includes qty and sugar toggle)
    delivered = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

# Endpoint 1: Store a new order
@app.route('/store_order', methods=['POST'])
def store_order():
    data = request.get_json()
    order_data = Order(
        mode=data.get('mode', 'desk'),
        name=data.get('name'),
        emp_code=data.get('emp_code'),
        room_no=data.get('room_no'),
        order_json=json.dumps(data.get('order', []))
    )
    db.session.add(order_data)
    db.session.commit()
    return jsonify({'message': 'Order stored successfully'}), 200

# Endpoint 2: Get all undelivered orders
@app.route('/get_recent_orders', methods=['GET'])
def get_recent_orders():
    orders = Order.query.filter_by(delivered=False).order_by(Order.timestamp.desc()).limit(20).all()
    result = []
    for o in orders:
        result.append({
            'id': o.id,
            'timestamp': o.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'mode': o.mode,
            'name': o.name,
            'emp_code': o.emp_code,
            'room_no': o.room_no,
            'order': json.loads(o.order_json)
        })
    return jsonify(result), 200

# Endpoint 3: Mark as delivered
@app.route('/mark_delivered', methods=['POST'])
def mark_delivered():
    data = request.get_json()
    order_id = data.get('id')
    order = Order.query.get(order_id)
    if order:
        order.delivered = True
        db.session.commit()
        return jsonify({'message': 'Order marked as delivered'}), 200
    else:
        return jsonify({'error': 'Order not found'}), 404

# ✅ Endpoint 4: Get all orders (with optional date filters)
@app.route('/all_orders', methods=['GET'])
def all_orders():
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    query = Order.query

    if start_date:
        query = query.filter(Order.timestamp >= start_date)
    if end_date:
        query = query.filter(Order.timestamp <= end_date)

    query = query.order_by(Order.timestamp.desc())

    orders = query.all()
    result = []
    for o in orders:
        result.append({
            'id': o.id,
            'timestamp': o.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'mode': o.mode,
            'name': o.name,
            'emp_code': o.emp_code,
            'room_no': o.room_no,
            'delivered': o.delivered,
            'order': json.loads(o.order_json)
        })
    return jsonify(result), 200

# Run the app
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
