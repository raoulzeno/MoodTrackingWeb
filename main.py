import os
import jwt
import csv
import io
from jwt import PyJWKClient
from functools import wraps
from sqlalchemy.orm import selectinload, joinedload
from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
from supabase import create_client, Client
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy import or_
from datetime import datetime, timedelta
from dotenv import load_dotenv
from weather import get_weather
from collections import Counter, defaultdict

load_dotenv()
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SECRET_KEY")
supabase: Client = create_client(supabase_url, supabase_key)
jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"

jwks_client = PyJWKClient(jwks_url)

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

entry_activities = db.Table('entry_activities',
    db.Column('entry_id', db.Integer, db.ForeignKey('mood_entries.id'), primary_key=True),
    db.Column('activity_id', db.Integer, db.ForeignKey('activities.id'), primary_key=True)
)

CORE_EMOTIONS = ["fear", "anger", "sadness", "neutral", "joy", "disgust", "surprise"]
CITY_COORDINATES = {
    "basel": {"lat": 47.5596, "lon": 7.5886},
    "zurich": {"lat": 47.3769, "lon": 8.5417},
    "winterthur": {"lat": 47.4991, "lon": 8.7291},
    "zollikerberg": {"lat": 47.3421, "lon": 8.5910},
    "nurnberg": {"lat": 49.4521, "lon": 11.0767},
    "lausen": {"lat": 47.4716, "lon": 7.7634}
}


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True)
    username = db.Column(db.String(50), nullable=False)

class MoodEntry(db.Model):
    __tablename__ = "mood_entries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
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

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

class Substance(db.Model):
    __tablename__ = "substances"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

class EntrySubstance(db.Model):
    __tablename__ = "entry_substances"
    entry_id = db.Column(db.Integer, db.ForeignKey("mood_entries.id"), primary_key=True)
    substance_id = db.Column(db.Integer, db.ForeignKey("substances.id"), primary_key=True)

    dosage = db.Column(db.Integer, nullable=False)

    substance = db.relationship("Substance")

def get_color_class(metric_type, score):
    if metric_type == "stress":
        if score >= 7: return "text-red-400 drop-shadow-[0_0_8px_rgba(248,113,113,0.4)]"
        if score >= 4: return "text-yellow-400 drop-shadow-[0_0_8px_rgba(250,204,21,0.3)]"
        return "text-green-400 drop-shadow-[0_0_10px_rgba(74,222,128,0.3)]"
    
    else:
        if score >= 7: return "text-green-400 drop-shadow-[0_0_10px_rgba(74,222,128,0.3)]"
        if score >= 4: return "text-yellow-400 drop-shadow-[0_0_8px_rgba(250,204,21,0.3)]"
        return "text-red-400 drop-shadow-[0_0_8px_rgba(248,113,113,0.4)]"

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            parts = request.headers["Authorization"].split()
            if len(parts) == 2:
                token = parts[1]
        
        if not token:
            return jsonify({"status" : "error", "message" : "Authentication token is missing"}), 401
        
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            decoded_token = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience="authenticated"
            )

            current_user_id = decoded_token["sub"]
        except jwt.ExpiredSignatureError:
            return jsonify({"status": "error", "message": "Token has expired"}), 401
        except Exception as e:
            print(f"\n JWT REJECTION CAUSE: {str(e)}\n")
            return jsonify({"status" : "error", "message" : "Invalid token"}), 401

        return f(current_user_id, *args, **kwargs)
    return decorated

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/export-user-data")
@token_required
def export_user_data(current_user_id):
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id
    ).order_by(MoodEntry.timestamp.desc()).all()

    si = io.StringIO()
    cw = csv.writer(si)

    cw.writerow([
        "Date", "Time", "Entry Type", "Mood", "Energy", "Stress", "Sleep Quality", "Sleep Time", "Primary Emotion", "Secondary Emotion", "Work Hours", "Work Place", "Social Context", "Location", "Notes", "Weather"
    ])

    for e in entries:
        date_str = e.timestamp.strftime("%Y-%m-%d") if e.timestamp else "N/A"
        time_str = e.timestamp.strftime("%H:%M") if e.timestamp else "N/A"
        
        cw.writerow([
            date_str,
            time_str,
            e.entry_type,
            e.mood,
            e.energy,
            e.stress,
            e.sleep_quality or "",
            e.sleep_time or "",
            e.primary_emotion or "",
            e.secondary_emotion or "",
            e.work_hours or "",
            e.work_place or "",
            e.social_context or "",
            e.location or "",
            e.notes or "",
            e.weather_condition or ""
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=mood_tracker_export.csv"
    output.headers["Content-type"] = "text/csv"

    return output


@app.route("/api/user-tracking-items", methods=["GET"])
@token_required
def get_tracking_items(current_user_id):
    activities = db.session.query(Activity).filter(
        or_(Activity.user_id == current_user_id, Activity.user_id.is_(None))
    )

    substances = db.session.query(Substance).filter(
        or_(Substance.user_id == current_user_id, Substance.user_id.is_(None))
    )

    return jsonify({
        "status" : "success",
        "activities" : [{"id" : a.id, "name" : a.name} for a in activities],
        "substances" : [{"id": s.id, "name": s.name} for s in substances]
    }), 200

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/edit-logs")
def edit_logs():
    return render_template("edit-logs.html")

@app.route("/update-password")
def update_page():
    return render_template("update-password.html")

@app.route("/signup")
def signup_page():
    return render_template("signup.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/detail")
def detail_log():
    return render_template("detail-log.html")

@app.route("/visualizations")
def visualization():
    return render_template("visualizations.html")

@app.route("/notes-feed")
def notes_feed():
    return render_template("notes-feed.html")

@app.route("/get-weather", methods=["GET"])
def fetch_weather():
    try:
        city = request.args.get("city", "Zurich")
        clean_city = city.strip().lower().replace("ü", "u").replace("ö", "o")
        coords = CITY_COORDINATES.get(clean_city, CITY_COORDINATES["zurich"])
        latitude = coords["lat"]
        longitude = coords["lon"]
        weather_string = get_weather(longitude=longitude, latitude=latitude)
        if not weather_string:
            return jsonify({"status": "success", "weather": "☀️ 21°C"}), 200
            
        return jsonify({"status": "success", "weather" : weather_string}), 200
    except Exception as e:
        return jsonify({"status": "success", "weather": "☀️ 21°C"}), 200

@app.route("/get-timestamps", methods=["GET"])
@token_required
def get_timestamps(current_user_id):
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
    ).order_by(MoodEntry.timestamp.desc()).all()
    
    logs = []
    for e in entries:
        entry_dict = {
            "id" : e.id,
            "date" : e.timestamp.strftime("%a, %d %b %Y")
        }
        logs.append(entry_dict)

    data = {
        "status" : "success",
        "logs" : logs
    }

    return jsonify(data), 200

@app.route("/edit-log/<int:entry_id>")
def edit_specific_log_page(entry_id):
    return render_template("edit-specific-log.html", entry_id=entry_id)

@app.route("/api/get-single-log/<int:entry_id>", methods=["GET"])
@token_required
def get_single_log(current_user_id, entry_id):
    entry = MoodEntry.query.filter_by(id=entry_id, user_id=current_user_id).first()

    if not entry:
        return jsonify({"status": "error", "message": "Log not found"}), 404

    return jsonify({
        "status" : "success",
        "mood" : entry.mood,
        "energy" : entry.energy,
        "stress" : entry.stress,
        "sleep_quality" : entry.sleep_quality,
        "sleep_time" : entry.sleep_time,
        "primary_emotion" : entry.primary_emotion,
        "secondary_emotion" : entry.secondary_emotion,
        "work_hours" : entry.work_hours,
        "work_place" : entry.work_place,
        "social_context" : entry.social_context,
        "location" : entry.location,
        "notes" : entry.notes,
        "date" : entry.timestamp.strftime("%a, %d %b %Y")
    }), 200

@app.route("/api/delete-account", methods=["DELETE"])
@token_required
def delete_account(current_user_id):
    try: 
        entries = MoodEntry.query.filter_by(user_id=current_user_id).all()
        for entry in entries:
            db.session.delete(entry)

        Activity.query.filter_by(user_id=current_user_id).delete()
        Substance.query.filter_by(user_id=current_user_id).delete()

        user_record = User.query.get(current_user_id)
        if user_record:
            db.session.delete(user_record)

        db.session.commit()

        supabase.auth.admin.delete_user(current_user_id)

        return jsonify({"status" : "success", "message" : "Account deleted."}), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting account: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to delete account."}), 500

@app.route("/api/update-log/<int:entry_id>", methods=["PUT"])
@token_required
def update_specific_log(current_user_id, entry_id):
    data = request.json

    entry = MoodEntry.query.filter_by(id=entry_id, user_id=current_user_id).first()
    if not entry:
        return jsonify({"status" : "error", "message" : "Log not found"}), 404
    
    try:
        entry.mood = data.get("mood", entry.mood)
        entry.energy = data.get("energy", entry.energy)
        entry.stress = data.get("stress", entry.stress)
        entry.sleep_quality = data.get("sleep_quality", entry.sleep_quality)
        entry.sleep_time = data.get("sleep_time", entry.sleep_time)
        entry.primary_emotion = data.get("primary_emotion", entry.primary_emotion)
        entry.secondary_emotion = data.get("secondary_emotion", entry.secondary_emotion)
        entry.work_hours = data.get("work_hours", entry.work_hours)
        entry.work_place = data.get("work_place", entry.work_place)
        entry.social_context = data.get("social_context", entry.social_context)
        entry.location = data.get("location", entry.location)
        entry.notes = data.get("notes", entry.notes)

        activity_ids = data.get("activities", [])
        if activity_ids:
            new_activities = Activity.query.filter(Activity.id.in_(activity_ids)).all()
            entry.activities = new_activities
        else:
            entry.activities = []

        substances_data = data.get("substances", [])
        EntrySubstance.query.filter_by(entry_id=entry.id).delete()

        for sub in substances_data:
            new_substance_log = EntrySubstance(
                entry_id = entry.id,
                substance_id=sub["id"],
                dosage=sub["dosage"]
            )
            db.session.add(new_substance_log)
        
        db.session.commit()
        return jsonify({"status" : "success", "message" : "Log updated successfully"}), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"Error updating log: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to update log"}), 500

@app.route("/save-quick-log", methods=["POST"])
@token_required
def save_quick_log(current_user_id):
    data = request.get_json()

    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    existing_entry = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.timestamp >= start_of_today
    ).first()

    if existing_entry:
        return jsonify({
            "status": "error",
            "message": "You have already logged an entry today! Come back tomorrow."
        }), 400

    new_entry = MoodEntry(
        user_id=current_user_id,
        entry_type="quick",
        mood=data["mood"],
        energy=data["energy"],
        stress=data["stress"]
    )

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({"status" : "success", "message" : "Entry saved."}), 200

@app.route("/save-detail-log", methods=["POST"])
@token_required
def save_detail_log(current_user_id):
    data = request.get_json()
    weather_from_frontend = data.get("weather")
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    existing_entry = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.timestamp >= start_of_today
    ).first()

    if existing_entry:
        if existing_entry.entry_type == "detailed":
            return jsonify({"status" : "error", "message" : "Already saved a Detail Log! Come back tomorrow."}), 400
        
        elif existing_entry.entry_type == "quick":
            db.session.delete(existing_entry)
            db.session.flush()
    user_city = user_city = data.get("city", "zurich").strip().lower().replace("ü", "u").replace("ö", "o")

    coords = CITY_COORDINATES.get(user_city, CITY_COORDINATES["zurich"])


    raw_weather = get_weather(longitude=coords["lon"], latitude=coords["lat"])
    clean_weather = raw_weather[2:] if raw_weather else None

    new_entry = MoodEntry(
        user_id=current_user_id,
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
        weather_condition=weather_from_frontend
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
@token_required
def delete_entry(current_user_id):
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    entry_to_delete = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
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
@token_required
def get_quicklog_values(current_user_id):
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    entry = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
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

@app.route("/get-notes-data", methods=["GET"])
@token_required 
def get_notes_data(current_user_id):
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.notes.isnot(None)
    ).order_by(MoodEntry.timestamp.desc()).limit(20).all()

    if not entries: return jsonify({
        "status" : "success",
        "data" : {}
    }), 200

    data_list = [{
        "date": e.timestamp.strftime("%b %d, %Y"),
        "mood": e.mood,
        "energy": e.energy,
        "stress": e.stress,
        "note": e.notes
    } for e in entries]
    return jsonify({
        "status" : "success",
        "data" : data_list
    }), 200
    


@app.route("/get-averages", methods=["GET"])
@token_required
def get_weekly_averages(current_user_id):
    start_of_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    end_of_time = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    stats = db.session.query(
        func.avg(MoodEntry.mood).label("avg_mood"),
        func.avg(MoodEntry.energy).label("avg_energy"),
        func.avg(MoodEntry.stress).label("avg_stress")
    ).filter(
        MoodEntry.user_id == current_user_id,
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
        "mood_color" : get_color_class("mood", stats.avg_mood),
        "energy_score": round(stats.avg_energy, 1),
        "energy_color" : get_color_class("energy", stats.avg_energy),
        "stress_score" : round(stats.avg_stress, 1),
        "stress_color" : get_color_class("stress", stats.avg_stress)
    }), 200

@app.route("/get-trend-data", methods=["GET"])
@token_required
def get_trend_data(current_user_id):
    seven_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)

    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.timestamp >= seven_days_ago
    ).all()

    daily_data = {}
    for i in range(7):
        day_date = seven_days_ago + timedelta(days=i)
        day_str = day_date.strftime("%a")
        daily_data[day_str] = {"mood" : [], "energy" : [], "stress" : []}

    for e in entries:
        day_str = e.timestamp.strftime("%a")
        if day_str in daily_data:
            daily_data[day_str]["mood"].append(e.mood)
            daily_data[day_str]["energy"].append(e.energy)
            daily_data[day_str]["stress"].append(e.stress)

    labels = []
    moods = []
    energies = []
    stress = []

    for i in range(7):
        day_date = seven_days_ago + timedelta(days=i)
        day_str = day_date.strftime("%a")
        labels.append(day_str)
        
        m_list = daily_data[day_str]["mood"]
        e_list = daily_data[day_str]["energy"]
        s_list = daily_data[day_str]["stress"]

        moods.append(round(sum(m_list)/len(m_list), 1) if m_list else None)
        energies.append(round(sum(e_list)/len(e_list), 1) if e_list else None)
        stress.append(round(sum(s_list)/len(s_list), 1) if s_list else None)
    
    data = {
        "labels": labels,
        "moods": moods,
        "energies": energies,
        "stress": stress
    }

    return jsonify(data), 200

@app.route("/get-work-data", methods=["GET"])
@token_required
def get_work_data(current_user_id):
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)

    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
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
@token_required
def get_env_data(current_user_id):
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
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

@app.route("/get-cal-month-data", methods=["GET"])
@token_required
def get_cal_data(current_user_id):
    year_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365)
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.timestamp >= year_ago
    ).order_by(MoodEntry.timestamp.asc()).all()

    if not entries:
        return jsonify({
            "status" : "success",
            "mood_objs" : []
        }), 200
    
    mood_objs = []
    for e in entries:
        obj = { "date": e.timestamp.strftime("%Y-%m-%d"), "value" : e.mood}
        mood_objs.append(obj)

    data = {
        "status" : "success",
        "mood_objs" : mood_objs
    }
    
    return jsonify(data), 200

@app.route("/get-emotion-data", methods=["GET"])
@token_required
def get_emotion_data(current_user_id):
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365)
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.timestamp >= thirty_days_ago
    ).order_by(MoodEntry.timestamp.asc()).all()

    if not entries:
        return jsonify({
            "status" : "success",
            "data" : []
        }), 200
    
    emotion_pairs = [(e.primary_emotion, e.secondary_emotion) for e in entries if e.primary_emotion and e.secondary_emotion]

    pair_counts = Counter(emotion_pairs)

    series_data = []

    for primary in CORE_EMOTIONS:
        data_points = []
        for secondary in CORE_EMOTIONS:
            count = pair_counts.get((primary, secondary), 0)

            data_points.append({
                "x" : secondary.capitalize(),
                "y" : count
            })
        series_data.append({
            "name" : primary.capitalize(),
            "data" : data_points
        })
    
    return jsonify({
        "status" : "success",
        "data" : series_data
    }), 200

@app.route("/get-sleep-data", methods=["GET"])
@token_required
def get_sleep_data(current_user_id):
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365)
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.timestamp >= thirty_days_ago
    ).all()

    if not entries: return jsonify({
        "status": "success",
        "moods" : [],
        "sleep-hours": [],
        "sleep-quality" : []
    })

    sleep_quality_map = defaultdict(list) # sleep_quality_map = {(hours, quality) : [mood1, mood2]

    for e in entries:
        sleep_quality_map[(e.sleep_time, e.sleep_quality)].append(e.mood)

    series_data = []

    for quality in ["good", "okay", "bad"]:
        data_points = []
        for (sleep_time, sleep_quality), moods in sleep_quality_map.items():
            if sleep_quality == quality:
                data_obj = {
                    "x" : sleep_time,
                    "y" : sum(moods) / len(moods)
                }
                data_points.append(data_obj)
        series_obj = {
            "label": quality.capitalize() + "" + "Quality",
            "data" : data_points
        }

        series_data.append(series_obj)



    return jsonify({
        "status" : "success",
        "data" : series_data,
    }), 200

@app.route("/get-work-insights", methods=["GET"])
@token_required
def get_work_insights(current_user_id):
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    entries = MoodEntry.query.filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.timestamp >= thirty_days_ago,
        MoodEntry.work_hours.isnot(None)
    ).all()

    if not entries: return jsonify({
        "status" : "success",
        "data" : {},
        "insights": "No insights to date."
    }), 200


    mood_buckets = {"light" : [], "optimal" : [], "heavy" : []}
    energy_buckets = {"light" : [], "optimal" : [], "heavy" : []}
    stress_buckets = {"light" : [], "optimal" : [], "heavy" : []}

    for e in entries:
        if e.work_hours < 6:
            mood_buckets["light"].append(e.mood)
            energy_buckets["light"].append(e.energy)
            stress_buckets["light"].append(e.stress)
        elif 6 <= e.work_hours < 9:
            mood_buckets["optimal"].append(e.mood)
            energy_buckets["optimal"].append(e.energy)
            stress_buckets["optimal"].append(e.stress)
        else:
            mood_buckets["heavy"].append(e.mood)
            energy_buckets["heavy"].append(e.energy)
            stress_buckets["heavy"].append(e.stress)

    def safe_avg(lst):
        return sum(lst) / len(lst) if len(lst) > 0 else 0

    avg_moods = {k: safe_avg(v) for k, v in mood_buckets.items()}
    avg_energies = {k: safe_avg(v) for k, v in energy_buckets.items()}
    avg_stresses = {k: safe_avg(v) for k, v in stress_buckets.items()}

    valid_moods = {k: v for k,v in avg_moods.items() if v > 0}
    valid_energies = {k: v for k,v in avg_energies.items() if v > 0}
    valid_stresses = {k: v for k,v in avg_stresses.items() if v > 0}

    max_mood = max(valid_moods.values()) if valid_moods else 0
    max_energy = max(valid_energies.values()) if valid_energies else 0
    min_stress = min(valid_stresses.values()) if valid_stresses else 0

    best_mood_loads = [k for k, v in valid_moods.items() if v == max_mood]
    best_energy_loads = [k for k, v in valid_energies.items() if v == max_energy]
    best_stress_loads = [k for k, v in valid_stresses.items() if v == min_stress] 

    def create_insights(loads, logged):
        logged_map = {
            "mood" : "best",
            "energy" : "most energetic",
            "stress" : "least stressed"
        }

        worked_map = {
            "light" : "less than 6 hours",
            "optimal" : "between 6 and 9 hours",
            "heavy" : "more than 9 hours"
        }
        if len(loads) == 1:
            value = loads[0]
            insight = f"You feel {logged_map[logged]} when working {worked_map[value]}."
            return insight
        
        elif len(loads) == 2:
            insight = f"You feel {logged_map[logged]} when working either {worked_map[loads[0]]} or {worked_map[loads[1]]}."
            return insight
        
        else:
            return f"You don't seem to have a preference in terms of {logged}."

    insights = {
        "mood" : create_insights(best_mood_loads, "mood"),
        "energy" : create_insights(best_energy_loads, "energy"),
        "stress" : create_insights(best_stress_loads, "stress")
    }

    data = {
        "labels" : ["< 6 hours", "6 to 9 hours", "9+ hours"],
        "datasets" : [{
            "label" : "Mood", 
            "data" : [avg_moods["light"], avg_moods["optimal"], avg_moods["heavy"]]
        }, {
            "label" : "Energy",
            "data" : [avg_energies["light"], avg_energies["optimal"], avg_energies["heavy"]]
        }, {
            "label" : "Stress",
            "data" : [avg_stresses["light"], avg_stresses["optimal"], avg_stresses["heavy"]]
        }]
    }

    return jsonify({
        "status" : "success",
        "data" : data,
        "insights" : insights
    }), 200


@app.route("/get-activities-and-substances", methods=["GET"])
@token_required
def get_act_subst(current_user_id):
    thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    entries = MoodEntry.query.options(
        selectinload(MoodEntry.activities),
        selectinload(MoodEntry.substances).joinedload(EntrySubstance.substance)
    ).filter(
        MoodEntry.user_id == current_user_id,
        MoodEntry.timestamp >= thirty_days_ago
    ).all()

    if not entries: return jsonify({
        "status" : "success",
        "activity_obj" : [],
        "substance_obj" : []
    }), 200

    moods = [e.mood for e in entries if e.mood]
    avg_mood_overall = sum(moods) / len(moods)

    activity_map = defaultdict(list)
    substance_map = defaultdict(list)

    for e in entries:
        if e.mood is None:
            continue
        if e.activities:
            act_list = [a.name for a in e.activities]
            for act in act_list:
                activity_map[act].append(e.mood)
        
        if e.substances:
            sub_list = [s.substance.name for s in e.substances]
            for sub in sub_list:
                substance_map[sub].append(e.mood)

    def calculate_influence(data_map):
        results = []
        for name, mood_list in data_map.items():
            avg_with_item = sum(mood_list) / len(mood_list)
            impact = round(avg_with_item - avg_mood_overall, 2)
            results.append({
                "name" : name,
                "impact" : impact,
                "count" : len(mood_list)
            })
        return sorted(results, key=lambda x: x["impact"], reverse=True)

    return jsonify({
        "status" : "success",
        "activities" : calculate_influence(activity_map),
        "substances" : calculate_influence(substance_map)
    }), 200

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if not User.query.get("test-admin-uuid-123"):
            dummy = User(id="test-admin-uuid-123", username="Admin")
            db.session.add(dummy)
            db.session.commit()
    
    app.run(host="0.0.0.0", port=5000, debug=True)