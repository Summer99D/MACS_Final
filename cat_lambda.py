# cat_lambda.py

def lambda_handler(event, context):
    user_id = event.get("user_id")
    responses = event.get("responses")
    time_spent = event.get("time_spent", 0)  # Time spent in seconds

    # Validity check
    if not responses or time_spent < 5:
        return {
            "user_id": user_id,
            "valid": False,
            "reason": "Incomplete or too fast"
        }

    phase = classify_phase(responses)
    
    return {
        "user_id": user_id,
        "phase": phase,
        "valid": True
    }


def classify_phase(res):
    """
    Takes the responses dictionary and returns one of the phases.
    Input Example:
    {
        "q1": 3,
        "q2": 1,
        "q3": 2,
        "q4": 1,
        "q5": ["Cramps", "Bloating"],
        "q6": 2,
        "q5_text": "Mild headache"
    }
    """
    bleeding = res.get("q1")                  # Menstrual bleeding (0–4)
    mucus = res.get("q2")                     # Cervical mucus consistency (0–4)
    libido = res.get("q3")                    # Sexual desire (1–5)
    mood = res.get("q4")                      # Mood (1–5)
    symptoms = res.get("q5", [])              # List of symptoms (checkbox) (the optional text box would not invalidate the survey if empty)
    energy = res.get("q6")                    # Energy (1–5)

    # Define symptom keywords associated with each phase
    menstruation_symptoms = ["Cramps", "Lower back pain", "Headache or migraine"]
    luteal_symptoms = ["Bloating", "Breast tenderness", "Breast fullness or swelling", "Digestive issues", "Acne or skin breakouts"]
    ovulation_symptoms = ["Feeling hot or flushed", "Egg-white consistency mucus", "High libido"]

    score = {"Menstruation": 0, "Luteal": 0, "Ovulation": 0, "Follicular": 0}

    # Heuristic 1: Bleeding
    if bleeding >= 2:
        score["Menstruation"] += 3
    elif bleeding == 1:
        score["Luteal"] += 1

    # Heuristic 2: Cervical mucus and libido
    if mucus == 4 or libido >= 4:
        score["Ovulation"] += 2
    elif mucus in [2, 3]:
        score["Follicular"] += 1

    # Heuristic 3: Energy
    if energy in [1, 2]:
        score["Menstruation"] += 1
        score["Luteal"] += 1
    elif energy >= 4:
        score["Ovulation"] += 1
        score["Follicular"] += 1

    # Heuristic 4: Loop through symptoms
    for symptom in symptoms:
        if symptom in menstruation_symptoms:
            score["Menstruation"] += 1
        elif symptom in luteal_symptoms:
            score["Luteal"] += 1
        elif symptom in ovulation_symptoms:
            score["Ovulation"] += 1

    # Final decision
    assigned_phase = max(score, key=score.get)

    return assigned_phase