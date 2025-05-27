# rec_lambda.py

def lambda_handler(event, context):
    user_id = event.get("user_id")
    phase = event.get("phase")

    recommendations = generate_recommendations(phase)

    return {
        "user_id": user_id,
        "phase": phase,
        "recommendations": recommendations
    }


def generate_recommendations(phase):
    recs = {
        "Menstruation": [
            "Get plenty of rest and iron-rich foods like spinach and lentils.",
            "Do gentle yoga or stretching instead of high-intensity workouts.",
            "Stay hydrated and use heat pads for cramps."
        ],
        "Follicular": [
            "Try new activities; your brain is in a great learning state.",
            "Add lean protein and colorful vegetables to your meals.",
            "Great time for strength training or cardio workouts."
        ],
        "Ovulation": [
            "Eat zinc-rich foods like pumpkin seeds for hormone support.",
            "Socialize and schedule big meetings—confidence peaks now.",
            "Engage in high-intensity or group workouts."
        ],
        "Luteal": [
            "Eat magnesium-rich foods (dark chocolate, leafy greens) to ease PMS.",
            "Practice mindfulness or journaling to regulate mood.",
            "Switch to moderate exercise like pilates or walking."
        ],
        "Unknown": [
            "Unable to identify your phase. Try submitting again tomorrow.",
            "Make sure your responses are complete and accurate."
        ]
    }
    return recs.get(phase, recs["Unknown"])