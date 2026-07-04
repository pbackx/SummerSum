import os
import json
import io
import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image
from google import genai
from google.genai import types

# Import our Pydantic model for structured grading
from app.agent import evaluator_agent, EvaluationResult, math_coach_agent
from app import firebase_db
from firebase_admin import auth
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import vertexai

app = FastAPI(title="SummerSum Math Coach API")

# Initialize vertexai client and declare remote agent global variables
vertexai.init(project="summersum-agent-dev", location="us-east1")
vertex_client = vertexai.Client(project="summersum-agent-dev", location="us-east1")
remote_agent = None

# Initialize stateful session service for the ADK agent
session_service = InMemorySessionService()

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize GenAI Client using Vertex AI with ADC
client = genai.Client(vertexai=True, project="summersum-agent-dev", location="us-central1")

@app.on_event("startup")
def startup_event():
    global remote_agent
    # Migrate questions to Firestore if collection is empty
    firebase_db.migrate_questions_to_firestore()
    
    # Load remote Reasoning Engine ID from deployment_metadata.json
    try:
        metadata_path = "deployment_metadata.json"
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                meta = json.load(f)
                engine_id = meta["remote_agent_runtime_id"]
                print(f"Loading remote Vertex AI agent: {engine_id}")
                remote_agent = vertex_client.agent_engines.get(name=engine_id)
        else:
            print("Warning: deployment_metadata.json not found. Deployed agent will not be available.")
    except Exception as e:
        print(f"Error loading remote agent Reasoning Engine: {e}")

# Firebase Authentication Dependency
def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token["uid"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase ID Token: {e}"
        )

def get_admin_user(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    try:
        decoded_token = auth.verify_id_token(token)
        email = decoded_token.get("email")
        if email != "peter.backx@gmail.com":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Admin privileges required."
            )
        return decoded_token["uid"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase ID Token: {e}"
        )

@app.get("/api/admin/data")
def get_admin_data(user_id: str = Depends(get_admin_user)):
    return {
        "status": "success",
        "message": "Welkom in het beheerderspaneel, Peter!",
        "admin_email": "peter.backx@gmail.com",
        "server_time": datetime.datetime.now().isoformat()
    }

# Firebase configuration endpoint for the frontend client
@app.get("/api/config")
def get_config():
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", "summersum-agent-dev"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", "")
    }

@app.get("/api/questions")
def get_all_questions(user_id: str = Depends(get_current_user)):
    return firebase_db.get_all_questions()

@app.get("/api/progress")
def get_student_progress(user_id: str = Depends(get_current_user)):
    return firebase_db.get_student_stats(user_id)

@app.get("/api/next_question")
async def get_next_question(user_id: str = Depends(get_current_user)):
    question = firebase_db.get_next_question_for_user(user_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No questions found in database. Run extraction first."
        )
    
    # Initialize the ADK session for the math coach
    session_id = f"session_{user_id}"
    try:
        await session_service.delete_session(app_name="app", user_id=user_id, session_id=session_id)
    except Exception:
        pass
        
    remote_session_id = None
    if remote_agent:
        try:
            # Create a remote session on Vertex AI Agent Runtime with GCS URIs in state
            remote_sess = await remote_agent.async_create_session(
                user_id=user_id,
                config={
                    "session_state": {
                        "question_image_gcs": question.get("question_image_gcs", ""),
                        "solution_image_gcs": question.get("solution_image_gcs", ""),
                        "status": "active"
                    }
                }
            )
            remote_session_id = remote_sess.get("id")
            print(f"Created remote session on Vertex AI: {remote_session_id}")
        except Exception as e:
            print(f"Error creating remote session on Vertex AI: {e}")

    await session_service.create_session(
        app_name="app",
        user_id=user_id,
        session_id=session_id,
        state={
            "current_question_id": question["id"],
            "remote_session_id": remote_session_id,
            "question_image_gcs": question.get("question_image_gcs", ""),
            "solution_image_gcs": question.get("solution_image_gcs", ""),
            "question_image_url": question.get("question_image_url", ""),
            "solution_image_url": question.get("solution_image_url", ""),
            "status": "active"
        }
    )
    
    return question

@app.post("/api/submit")
async def submit_solution(
    question_id: str = Form(...),
    student_answer_text: Optional[str] = Form(None),
    student_answer_file: Optional[UploadFile] = File(None),
    user_id: str = Depends(get_current_user)
):
    question = firebase_db.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
        
    session_id = f"session_{user_id}"
    session = await session_service.get_session(app_name="app", user_id=user_id, session_id=session_id)
    
    # If session doesn't exist or is for a different question, initialize it
    if not session or session.state.get("current_question_id") != question_id:
        try:
            await session_service.delete_session(app_name="app", user_id=user_id, session_id=session_id)
        except Exception:
            pass
            
        remote_session_id = None
        if remote_agent:
            try:
                # Create a remote session on Vertex AI Agent Runtime
                remote_sess = await remote_agent.async_create_session(
                    user_id=user_id,
                    config={
                        "session_state": {
                            "question_image_gcs": question.get("question_image_gcs", ""),
                            "solution_image_gcs": question.get("solution_image_gcs", ""),
                            "status": "active"
                        }
                    }
                )
                remote_session_id = remote_sess.get("id")
                print(f"Created remote session on fallback: {remote_session_id}")
            except Exception as e:
                print(f"Error creating remote session on fallback: {e}")

        session = await session_service.create_session(
            app_name="app",
            user_id=user_id,
            session_id=session_id,
            state={
                "current_question_id": question_id,
                "remote_session_id": remote_session_id,
                "question_image_gcs": question.get("question_image_gcs", ""),
                "solution_image_gcs": question.get("solution_image_gcs", ""),
                "question_image_url": question.get("question_image_url", ""),
                "solution_image_url": question.get("solution_image_url", ""),
                "status": "active"
            }
        )
        
    # Build user message parts
    message_parts = []
    if student_answer_text:
        message_parts.append(types.Part.from_text(text=student_answer_text))
    if student_answer_file:
        file_bytes = await student_answer_file.read()
        message_parts.append(types.Part.from_bytes(data=file_bytes, mime_type="image/png"))
        
    new_message = types.Content(role="user", parts=message_parts)
    
    coach_response = ""
    remote_session_id = session.state.get("remote_session_id")
    is_correct = False
    
    if remote_agent and remote_session_id:
        print(f"Sending message to remote Vertex AI agent (session: {remote_session_id})")
        try:
            async for event in remote_agent.async_stream_query(
                user_id=user_id,
                session_id=remote_session_id,
                message=new_message.parts
            ):
                if isinstance(event, dict):
                    content = event.get("content", {})
                    parts = content.get("parts", []) if isinstance(content, dict) else (content.parts if hasattr(content, "parts") else [])
                    for part in parts:
                        part_dict = part if isinstance(part, dict) else (part.model_dump() if hasattr(part, "model_dump") else {})
                        if "text" in part_dict:
                            coach_response += part_dict["text"]
                else:
                    content = getattr(event, "content", None)
                    if content and hasattr(content, "parts"):
                        for part in content.parts:
                            if hasattr(part, "text") and part.text:
                                coach_response += part.text
                                
            # Get remote session state to check correctness status
            remote_sess = await remote_agent.async_get_session(user_id=user_id, session_id=remote_session_id)
            remote_state = remote_sess.get("state", {}) if isinstance(remote_sess, dict) else getattr(remote_sess, "state", {})
            is_correct = (remote_state.get("status") == "correct")
        except Exception as e:
            print(f"Error querying remote agent: {e}")
            coach_response = ""
            
    if not coach_response:
        print("Using fallback local runner execution.")
        runner = Runner(agent=math_coach_agent, app_name="app", session_service=session_service)
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message
        ):
            if event.is_final_response() and event.content and event.content.parts:
                coach_response = "".join(part.text for part in event.content.parts if part.text)
                
        session = await session_service.get_session(app_name="app", user_id=user_id, session_id=session_id)
        is_correct = (session.state.get("status") == "correct")
    
    explanation_text = ""
    if is_correct:
        # Save solution to database
        streak = firebase_db.submit_user_solution(user_id, question_id, is_correct=True)
        
        # Generate the step-by-step correct solution explanation using Gemini
        sol_gcs_uri = session.state.get("solution_image_gcs")
        if sol_gcs_uri:
            explain_prompt = "Geef een heldere, stapsgewijze wiskundige uitleg in het Nederlands van de oplossing getoond in deze afbeelding."
            try:
                # Call Gemini for a single-turn explanation using GCS URI directly!
                explain_response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Part.from_uri(file_uri=sol_gcs_uri, mime_type="image/png"),
                        explain_prompt
                    ]
                )
                explanation_text = explain_response.text
            except Exception as e:
                print(f"Error generating explanation: {e}")
                explanation_text = "Kon de gedetailleerde uitleg niet genereren. Bekijk de afbeelding hieronder voor de uitwerking."
    else:
        # If incorrect, get current streak without updating progress
        stats = firebase_db.get_student_stats(user_id)
        streak = stats.get("streak", 0)
        
    return {
        "question_id": question_id,
        "is_correct": is_correct,
        "feedback": coach_response,
        "explanation": explanation_text,
        "streak": streak
    }

# Mount static folders to serve question images and frontend files
app.mount("/data/questions", StaticFiles(directory="data/questions"), name="questions")

# Mount the frontend files
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
