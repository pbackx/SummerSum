import os
import json
import datetime
from typing import List, Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin if not already initialized
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

def migrate_questions_to_firestore():
    """Migrates questions from database.json to Firestore if the collection is empty."""
    db_path = "data/database.json"
    if not os.path.exists(db_path):
        print(f"Migration skipped: {db_path} does not exist.")
        return
        
    # Check if questions collection is empty
    docs = db.collection("questions").limit(1).get()
    if len(docs) > 0:
        print("Migration skipped: Firestore 'questions' collection is already populated.")
        return
        
    print("Starting migration of questions to Firestore...")
    with open(db_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
        
    # Batch write in chunks of 500
    batch = db.batch()
    count = 0
    for q in questions:
        # Convert any bounding boxes / dicts to Firestore nested structures
        doc_ref = db.collection("questions").document(q["id"])
        batch.set(doc_ref, q)
        count += 1
        if count % 500 == 0:
            batch.commit()
            batch = db.batch()
            
    if count % 500 != 0:
        batch.commit()
        
    print(f"Successfully migrated {count} questions to Firestore.")

def get_all_questions() -> List[Dict[str, Any]]:
    """Retrieves all questions from Firestore."""
    docs = db.collection("questions").stream()
    return [doc.to_dict() for doc in docs]

def get_question(question_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single question by its ID."""
    doc = db.collection("questions").document(question_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

def get_user_progress_map(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Retrieves all completed/attempted questions progress for a user."""
    progress_docs = db.collection("users").document(user_id).collection("progress").stream()
    return {doc.id: doc.to_dict() for doc in progress_docs}

def get_student_stats(user_id: str) -> Dict[str, Any]:
    """Retrieves student progress stats, streak, and daily history."""
    # 1. Fetch questions and user progress
    questions = get_all_questions()
    completed_questions = get_user_progress_map(user_id)
    
    # 2. Fetch user stats document
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    streak = 0
    daily_history = []
    
    if user_doc.exists:
        user_data = user_doc.to_dict()
        streak = user_data.get("streak", 0)
        daily_history = user_data.get("daily_history", [])
        
    # 3. Calculate statistics
    total_questions = len(questions)
    completed = len(completed_questions)
    correct_count = sum(1 for q in completed_questions.values() if q.get("status") == "correct")
    
    # Calculate performance by topic
    topic_stats = {}
    for q in questions:
        topic = q["topic"]
        if topic not in topic_stats:
            topic_stats[topic] = {"total": 0, "correct": 0, "attempts": 0}
        topic_stats[topic]["total"] += 1
        
        q_prog = completed_questions.get(q["id"])
        if q_prog:
            topic_stats[topic]["attempts"] += q_prog.get("attempts", 0)
            if q_prog.get("status") == "correct":
                topic_stats[topic]["correct"] += 1
                
    return {
        "streak": streak,
        "total_questions": total_questions,
        "completed": completed,
        "correct": correct_count,
        "topics": topic_stats,
        "history": daily_history
    }

def get_next_question_for_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Selects the next question for a user based on adaptive difficulty."""
    questions = get_all_questions()
    if not questions:
        return None
        
    completed_questions = get_user_progress_map(user_id)
    
    # Determine recent answers for difficulty adjustment (order by updated_at desc)
    # Filter out entries without updated_at
    valid_progress = [p for p in completed_questions.values() if "updated_at" in p]
    recent_progress = sorted(
        valid_progress, 
        key=lambda x: x["updated_at"], 
        reverse=True
    )[:3]
    
    correct_streak = sum(1 for r in recent_progress if r.get("status") == "correct")
    
    target_difficulty = "medium"
    if correct_streak == 3:
        target_difficulty = "hard"
    elif correct_streak <= 1 and len(recent_progress) > 0:
        target_difficulty = "easy"
        
    # Filter out questions already answered correctly
    uncompleted = [
        q for q in questions 
        if q["id"] not in completed_questions or completed_questions[q["id"]].get("status") != "correct"
    ]
    
    if not uncompleted:
        # If all questions are completed correctly, fallback to first question for review
        return questions[0]
        
    # Try to find a question matching the target difficulty
    candidates = [q for q in uncompleted if q["difficulty"] == target_difficulty]
    
    # Fallback if no matching difficulty candidates
    if not candidates:
        candidates = uncompleted
        
    # For simplicity, return the first candidate
    return candidates[0]

def submit_user_solution(user_id: str, question_id: str, is_correct: bool) -> int:
    """Updates user progress and stats in Firestore. Returns the updated streak."""
    # 1. Update the question progress document
    progress_ref = db.collection("users").document(user_id).collection("progress").document(question_id)
    progress_doc = progress_ref.get()
    
    attempts = 1
    old_status = "none"
    if progress_doc.exists:
        progress_data = progress_doc.to_dict()
        attempts = progress_data.get("attempts", 0) + 1
        old_status = progress_data.get("status", "none")
        
    status = "correct" if is_correct else "incorrect"
    
    progress_ref.set({
        "attempts": attempts,
        "status": status,
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    
    # 2. Update overall user stats (streak and daily history)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    streak = 0
    daily_history = []
    if user_doc.exists:
        user_data = user_doc.to_dict()
        streak = user_data.get("streak", 0)
        daily_history = user_data.get("daily_history", [])
        
    # Streak logic:
    if is_correct:
        # Increment streak if they answered correctly
        streak += 1
    else:
        # Reset streak ONLY if this was their first attempt at the question
        if attempts == 1:
            streak = 0
            
    # Daily history logic:
    today = datetime.date.today().isoformat()
    day_entry = next((d for d in daily_history if d.get("date") == today), None)
    if not day_entry:
        day_entry = {"date": today, "questions_solved": 0}
        daily_history.append(day_entry)
        
    if is_correct and old_status != "correct":
        # Only increment solved count if it wasn't already marked correct in a previous session
        day_entry["questions_solved"] += 1
        
    # Save user stats
    user_ref.set({
        "streak": streak,
        "last_active": today,
        "daily_history": daily_history
    }, merge=True)
    
    return streak
