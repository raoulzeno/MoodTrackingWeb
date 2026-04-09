import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)

class MoodEntry(db.Model):
    __tablename__ = "mood_entries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now())

    mood = db.Column(db.Integer, nullable=False)
    energy = db.Column(db.Integer, nullable=False)
    stress = db.Column(db.Integer, nullable=False)

    sleep_quality = db.Column(db.String(20), nullable=True)
    sleep_time = db.Column(db.Float, nullable=True)

    primary_emotion = db.Column(db.String(50), nullable=True)
    secondary_emotion = db.Column(db.String(50), nullable=True)

    work_hours = db.Column(db.Float, nullable=True)
    work_place = db.Column(db.String(50), nullable=True)

    social_context = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(50), nullable=True)

    notes = db.Column(db.Text, nullable=True)
    weather_condition = db.Column(db.String(100), nullable=True)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/detail")
def detail_log():
    return render_template("detail-log.html")

@app.route("/visualizations")
def visualization():
    return render_template("visualizations.html")

@app.route("/save-quick-log", methods=["POST"])
def save_quick_log():
    data = request.get_json()

    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    existing_entry = MoodEntry.query.filter(
        MoodEntry.user_id == 1,
        MoodEntry.timestamp >= start_of_today
    ).first()

    if existing_entry:
        return jsonify({
            "status": "error",
            "message": "You have already logged an entry today! Come back tomorrow."
        }), 400

    new_entry = MoodEntry(
        user_id=1,
        mood=data["mood"],
        energy=data["energy"],
        stress=data["stress"]
    )

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({"status" : "success", "message" : "Entry saved."}), 200

@app.route("/save-detail-log", methods=["POST"])
def save_detail_log():
    data = request.get_json()
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    existing_entry = MoodEntry.query.filer(
        MoodEntry.user_id ==1,
        MoodEntry.timestamp >= start_of_today
    ).first()

    if existing_entry:
        pass

@app.route("/delete-entry", methods=["DELETE"])
def delete_entry():
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    entry_to_delete = MoodEntry.query.filter(
        MoodEntry.user_id == 1,
        MoodEntry.timestamp.between(start_of_today, end_of_today)
    ).first()

    if not entry_to_delete:
        return jsonify({
            "status": "error",
            "message": "No entries to delete today!"
        }), 404
    
    db.session.delete(entry_to_delete)
    db.session.commit()

    return jsonify({"status": "success", "message": "Entry deleted."}), 200

@app.route("/get-quicklog-values", methods=["GET"])
def get_quicklog_values():
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    entry = MoodEntry.query.filter(
        MoodEntry.user_id == 1,
        MoodEntry.timestamp >= start_of_today
    ).first()

    if not entry:
        return jsonify({
            "status": "success",
            "mood_value" : "0",
            "energy_value" : "0",
            "stress_value" : "0"
        }), 200
    return jsonify({
        "status" : "success",
        "mood_value" : entry.mood,
        "energy_value" : entry.energy,
        "stress_value" : entry.stress
    }), 200



if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if not User.query.get(1):
            dummy = User(username="Admin")
            db.session.add(dummy)
            db.session.commit()
    
    app.run(debug=True)