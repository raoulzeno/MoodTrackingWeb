from main import app, db, Activity, Substance

with app.app_context():

    act1 = Activity(name="Work")
    act2 = Activity(name="Workout")
    act3 = Activity(name="Youtube/Film Watching")
    act4 = Activity(name="Doomscrolling")
    act5 = Activity(name="Going Out")
    act6 = Activity(name="Meditating")
    act7 = Activity(name="Travelling")
    act8 = Activity(name="Meeting Friends")
    act9 = Activity(name="Meeting Family")
    act10 = Activity(name="Transit")
    act11 = Activity(name="Studying")
    act12 = Activity(name="Napping")

    sub1 = Substance(name="Alcohol")
    sub2 = Substance(name="Caffeine")
    sub3 = Substance(name="Sugar")
    sub4 = Substance(name="Meds")

    db.session.add_all([act1, act2, act3, act4, act5, act6, act7, act8, act9, act10, act11, act12])
    db.session.add_all([sub1, sub2, sub3, sub4])

    db.session.commit()
