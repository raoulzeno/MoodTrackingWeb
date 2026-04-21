import random
from datetime import datetime, timedelta
from main import app, db, MoodEntry, User, Activity, Substance, EntrySubstance

PRIMARY_WEIGHTS = [
    1,
    5,
    10,
    50,
    25,
    1,
    8
]

SECONDARY_WEIGHTS = [
    12,
    10,
    15,
    40,
    15,
    2,
    6
]

uuid = "432b967e-21b4-418d-bea8-19a1a3bb99a8"

def seed_database():
    with app.app_context():
        print("🌱 Starting the 365-day seeding process...")

        # 1. Make sure our default user exists
        user = User.query.get(uuid)
        if not user:
            user = User(username="Admin_final")
            db.session.add(user)
            db.session.commit()

        # 2. Create Default Activities & Substances (If they don't exist yet)
        print("🛠️ Checking for default Activities and Substances...")
        default_activities = ["Yoga", "Reading", "Gaming", "Exercise", "Meditation", "Doomscrolling"]
        default_substances = ["Coffee", "Alcohol", "Sugar", "Medication"]

        for act_name in default_activities:
            if not Activity.query.filter_by(name=act_name).first():
                db.session.add(Activity(name=act_name, user_id=uuid))
        
        for sub_name in default_substances:
            if not Substance.query.filter_by(name=sub_name).first():
                db.session.add(Substance(name=sub_name, user_id=uuid))
        
        db.session.commit()

        # Fetch them all so we can randomly pick them later
        all_activities = Activity.query.all()
        all_substances = Substance.query.all()

        print("📊 Generating 30 days of data...")

        # 3. Generate 30 days of data
        for i in range(365):
            target_date = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0) - timedelta(days=i)

            # --- SLEEP LOGIC ---
            sleep_hours = round(random.randint(8, 19) / 2 , 1)
            quality = "good" if sleep_hours >= 7.5 else "okay" if sleep_hours >= 5.5 else "bad"

            # --- ENVIRONMENT & MOOD LOGIC ---
            is_workday = random.choice([True, True, True, True, True, False, False]) 
            
            if is_workday:
                work_hours = random.choice([2, 6, 8, 10, 12])
                location = random.choice(["work", "work", "home"])
                social_context = random.choice(["coworkers", "alone"])
                if work_hours <= 6:
                    mood, energy, stress = random.randint(5, 8), random.randint(0, 8), random.randint(4, 6)
                elif 6 < work_hours <= 9:
                    mood, energy, stress = random.randint(3, 6), random.randint(5, 8), random.randint(6, 8)
                elif work_hours > 9:
                    mood, energy, stress = random.randint(2, 4), random.randint(9, 10), random.randint(9, 10)
            else:
                work_hours = None
                location = random.choice(["home", "outdoors", "transit"])
                social_context = random.choice(["friends", "partner", "family"])
                mood, energy, stress = random.randint(6, 10), random.randint(6, 10), random.randint(2, 5)

            # 4. Create the entry object
            entry = MoodEntry(
                user_id=uuid,
                entry_type="detailed",
                timestamp=target_date,
                mood=mood,
                energy=energy,
                stress=stress,
                sleep_time=sleep_hours,
                sleep_quality=quality,
                work_hours=work_hours,
                location=location,
                social_context=social_context,
                primary_emotion=random.choices(["fear", "anger", "sadness", "neutral", "joy", "disgust", "surprise"], weights=PRIMARY_WEIGHTS, k=1)[0],
                secondary_emotion=random.choices(["fear", "anger", "sadness", "neutral", "joy", "disgust", "surprise"], weights=SECONDARY_WEIGHTS, k=1)[0]
            )

            # --- ADD JUNCTIONS ---
            
            # Activities
            daily_activities = random.sample(all_activities, k=random.randint(1, 3))
            for act in daily_activities:
                entry.activities.append(act)

            # Substances
            daily_substances = random.sample(all_substances, k=random.randint(0, 2))
            for sub in daily_substances:
                entry_sub = EntrySubstance(
                    substance=sub,
                    dosage=random.randint(1, 4) 
                )
                entry.substances.append(entry_sub)

            db.session.add(entry)

        db.session.commit()
        print("✅ Successfully injected 365 days of fresh data!")

if __name__ == "__main__":
    seed_database()