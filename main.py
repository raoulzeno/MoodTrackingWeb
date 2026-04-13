import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from dotenv import load_dotenv
from weather import get_weather

load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

entry_activities = db.Table('entry_activities',
    db.Column('entry_id', db.Integer, db.ForeignKey('mood_entries.id'), primary_key=True),
    db.Column('activity_id', db.Integer, db.ForeignKey('activities.id'), primary_key=True)
)

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

    activities = db.relationship("Activity", secondary=entry_activities, backref="entries")

    entry_type = db.Column(db.String(20), nullable=False)

    substances = db.relationship("EntrySubstance", backref="entry", cascade="all, delete-orphan")

class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

class Substance(db.Model):
    __tablename__ = "substances"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

class EntrySubstance(db.Model):
    __tablename__ = "entry_substances"
    entry_id = db.Column(db.Integer, db.ForeignKey("mood_entries.id"), primary_key=True)
    substance_id = db.Column(db.Integer, db.ForeignKey("substances.id"), primary_key=True)

    dosage = db.Column(db.Integer, nullable=False)

    substance = db.relationship("Substance")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/detail")
def detail_log():
    all_activities = db.session.query(Activity).all()
    all_substances = db.session.query(Substance).all()
    return render_template("detail-log.html", activities=all_activities, substances=all_substances)

@app.route("/visualizations")
def visualization():
    return render_template("visualizations.html")
@app.route("/get-weather", methods=["GET"])
def fetch_weather():
    weather_string = get_weather()
    if not weather_string:
        return jsonify({
            "status": "error",
            "message": "Unable to fetch weather data."
        }), 400
    return jsonify({
        "status": "success",
        "weather" : weather_string
    }), 200

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
        entry_type="quick",
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

    existing_entry = MoodEntry.query.filter(
        MoodEntry.user_id ==1,
        MoodEntry.timestamp >= start_of_today
    ).first()

    if existing_entry:
        if existing_entry.entry_type == "detailed":
            return jsonify({"status" : "error", "message" : "Already saved a Detail Log! Come back tomorrow."}), 400
        
        elif existing_entry.entry_type == "quick":
            db.session.delete(existing_entry)
            db.session.flush()

    new_entry = MoodEntry(
        user_id=1,
        entry_type="detailed",
        mood=data["mood"],
        energy=data["energy"],
        stress=data["stress"],
        sleep_quality=data["sleep_quality"],
        sleep_time=data["sleep_time"],
        primary_emotion=data["primary_emotion"],
        secondary_emotion=data["secondary_emotion"],
        work_hours=data["work_hours"],
        work_place=data["work_place"],
        social_context=data["social_context"],
        location=data["location"],
        notes=data["notes"],
        weather_condition=data["weather_condition"]
    )
    with db.session.no_autoflush:
        for act_id in data["activities"]:
            activity_obj = db.session.get(Activity, act_id)
            if activity_obj:
                new_entry.activities.append(activity_obj)

    with db.session.no_autoflush:
        for item in data["substances"]:
            substance_id = item["id"]
            dosage = item["dosage"]

            substance_obj = db.session.get(Substance, substance_id)

            if substance_obj:
                new_sub = EntrySubstance(
                    substance=substance_obj,
                    dosage=dosage
                )

                new_entry.substances.append(new_sub)

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({"status": "success", "message" : "Entry saved."}), 200

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
            "mood_value" : "5",
            "energy_value" : "5",
            "stress_value" : "5"
        }), 200
    return jsonify({
        "status" : "success",
        "mood_value" : entry.mood,
        "energy_value" : entry.energy,
        "stress_value" : entry.stress
    }), 200

@app.route("/get-averages", methods=["GET"])
def get_weekly_averages():
    start_of_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    end_of_time = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    stats = db.session.query(
        func.avg(MoodEntry.mood).label("avg_mood"),
        func.avg(MoodEntry.energy).label("avg_energy"),
        func.avg(MoodEntry.stress).label("avg_stress")
    ).filter(
        MoodEntry.user_id == 1,
        MoodEntry.timestamp.between(start_of_time, end_of_time)
    ).first()

    if stats.avg_mood is None:
        return jsonify({
            "status": "success",
            "mood_score": "-",
            "energy_score": "-",
            "stress_score": "-"
        }), 200

    return jsonify({
        "status" : "success",
        "mood_score" : round(stats.avg_mood, 1),
        "energy_score": round(stats.avg_energy, 1),
        "stress_score" : round(stats.avg_stress, 1)
    }), 200

@app.route("/get-trend-data", methods=["GET"])
def get_trend_data():
    seven_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)

    entries = MoodEntry.query.filter(
        MoodEntry.user_id == 1,
        MoodEntry.timestamp >= seven_days_ago
    ).order_by(MoodEntry.timestamp.asc()).all()

    if not entries:
        return jsonify({
            "labels": [],
            "moods": [],
            "energies": [],
            "stress": []
        }), 200
    
    data = {
        "labels": [e.timestamp.strftime("%a") for e in entries],
        "moods": [e.mood for e in entries],
        "energies": [e.energy for e in entries],
        "stress": [e.stress for e in entries]
    }

    return jsonify(data), 200

@app.route("/get-sleep-data", methods=["GET"])
def get_sleep_data():
    seven_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)

    entries = MoodEntry.query.filter(
        MoodEntry.user_id == 1,
        MoodEntry.timestamp >= seven_days_ago
    ).order_by(MoodEntry.timestamp.asc()).all()

    if not entries:
        return jsonify({
            "labels": [],
            "sleep_hours": [],
            "sleepquality": [],
            "moods": [],
            "energies": [],
            "stress": []
        }), 200
    
    data = {
        "labels": [e.timestamp.strftime("%a") for e in entries],
        "sleep_time": [e.sleep_time for e in entries],
        "sleep_quality": [e.sleep_quality for e in entries],
        "moods": [e.mood for e in entries],
        "energies": [e.energy for e in entries],
        "stress": [e.stress for e in entries]
    }

    return jsonify(data), 200

@app.route("/get-work-data", methods=["GET"])
def get_work_data():
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)

    entries = MoodEntry.query.filter(
        MoodEntry.user_id == 1,
        MoodEntry.timestamp >= thirty_days_ago
    ).order_by(MoodEntry.timestamp.asc()).all()

    scatter_data = []
    for e in entries:
        scatter_data.append({
            "x": e.work_hours,
            "y": e.mood,
            "date": e.timestamp.strftime("%b %d")
        })
    return jsonify({"data": scatter_data}), 200

@app.route("/get-environments-data", methods=["GET"])
def get_env_data():
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == 1,
        MoodEntry.timestamp >= thirty_days_ago
    ).all()

    categories = {
        "Home": lambda e: e.location == "home",
        "Work": lambda e: e.location == "work",
        "Outdoors": lambda e: e.location == "outdoors",
        "Transit" : lambda e: e.location == "transit",
        "Partner" : lambda e: e.social_context == "partner",
        "Friends" : lambda e: e.social_context == "friends",
        "Family" : lambda e: e.social_context == "family",
        "Alone" : lambda e: e.social_context == "alone",
        "Co-Workers": lambda e: e.social_context == "coworkers",
        "Strangers": lambda e: e.social_context == "strangers"
    }

    labels = []
    avg_moods = []
    avg_energies = []
    avg_stresses = []

    for name, condition in categories.items():
        matched_entries = [e for e in entries if condition(e)]

        if matched_entries:
            labels.append(name)
            avg_moods.append(round(sum(e.mood for e in matched_entries) / len(matched_entries), 1))
            avg_energies.append(round(sum(e.energy for e in matched_entries) / len(matched_entries), 1))
            avg_stresses.append(round(sum(e.stress for e in matched_entries) / len(matched_entries), 1))

    return jsonify({
        "labels": labels,
        "moods": avg_moods,
        "energies": avg_energies,
        "stress": avg_stresses
    }), 200



if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if not User.query.get(1):
            dummy = User(username="Admin")
            db.session.add(dummy)
            db.session.commit()
    
    app.run(debug=True)