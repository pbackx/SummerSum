# SummerSum - Your Personal Math Coach

SummerSum is an interactive web application designed to help students transitioning from the 2nd to the 3rd year of secondary school practice math during the summer holidays.

The application automatically extracts math questions and corresponding solutions from PDF exercise books, displays a new question to the student every day, and offers active, stateful guidance from a personal AI math coach.

---

## 📖 What the Application & Agent Do

### The Web Application
* **Daily Questions**: Students log in and receive one specific math question per day based on their progress.
* **Photo Upload**: Students can write down their calculations on paper, take a photo with their phone, and send it directly to the coach.
* **Progress & Streaks**: The app tracks how many questions the student has solved correctly and displays an active "daily streak" to boost motivation.
* **Admin Panel**: A secure page that allows administrators to view all questions in the database, laying the foundation to adjust question boundaries or parameters in the future.

### The AI Math Coach (ADK Agent)
* **Didactic Guidance**: Instead of revealing the solution immediately, the agent acts as a real coach. If a student gets stuck or gives an incorrect answer, the coach points out the error (e.g., "watch out for the minus sign") and asks guiding questions.
* **Multimodal Analysis**: The coach analyzes both typed text and uploaded photos of handwritten mathematical work.
* **Come Back Tomorrow**: As soon as the coach verifies that the student has solved the question 100% correctly, it calls the `mark_as_correct` tool. This triggers a streak increase and opens a step-by-step solution accordion on the frontend.

---

## 🛠️ Technical Architecture & Key Decisions

The application is built using a modern, robust cloud architecture:

```
[Frontend: HTML5, CSS3, JS] ---> (Firebase Authentication)
   |
   +---> [FastAPI Backend] ---> (Cloud Firestore)
            |
            +---> (Vertex AI Agent Runtime) ---> (Firebase Storage / GCS)
```

### 1. User Authentication (Google-Only Sign-In)
* **Decision**: The traditional email/password registration form was completely removed in favor of a single **"Continue with Google"** button.
* **Rationale**: This enhances security and provides a frictionless login experience for students and their parents, who almost always have a Google account.

### 2. Admin Panel Security
* **Decision**: Access to `admin.html` and the corresponding backend endpoint `/api/admin/data` is strictly restricted to the email address `peter.backx@gmail.com`.
* **Rationale**: Both on the client-side (app.js) and server-side (FastAPI dependency `get_admin_user`), the JWT claim in the Firebase ID token is checked to guarantee that unauthorized users cannot retrieve database records.

### 3. Database & Storage (Firestore & Google Cloud Storage)
* **Firestore**: Stores detailed metadata of all 153 math questions, as well as student progress statistics (streaks, list of solved questions).
* **Firebase Storage (GCS)**:
  * **Decision**: All cropped question and solution images, as well as the full PDF pages, were migrated to a Google Cloud Storage bucket (`summersum-agent-dev.firebasestorage.app`).
  * **Rationale**: Local disk storage does not work in serverless cloud environments (like Cloud Run). By storing files in GCS, the frontend loads them extremely fast directly from the Google CDN. Furthermore, the backend can send the `gs://` URIs directly to Gemini, saving server bandwidth and memory.
  * **Future UI**: By storing and linking the full PDF pages in Firestore, the database is prepared for an admin UI where administrators can visually adjust cropping boundaries (bounding boxes) in the future.

### 4. AI Orchestration (ADK & Vertex AI Agent Runtime)
* **Decision**: The agent is deployed to **Vertex AI Agent Runtime (Reasoning Engine)** in the `us-east1` region. The FastAPI backend acts as a proxy.
* **Rationale**:
  * Instead of stateless API calls, the cloud runtime manages the complete conversation history per session.
  * Hosting the agent on Google's Vertex AI runtime decouples the AI logic from the web server, demonstrating advanced usage of Google's Enterprise Agent Platform.
  * The backend communicates asynchronously via streaming (`async_stream_query`) with the Reasoning Engine and checks the session state afterwards (`async_get_session`) to see if the agent called the `mark_as_correct` tool.

---

## 🚀 Installation & Local Running

### Prerequisites
* **Python**: Version 3.11 or higher
* **Google Cloud SDK**: Configured with Application Default Credentials (ADC) and linked to the project `summersum-agent-dev`.
* **Firebase**: Firebase Storage and Cloud Firestore activated.

### 1. Configuration (`.env`)
Create a `.env` file in the root directory and fill in your Firebase and GCS credentials:
```env
FIREBASE_API_KEY="AIzaSy..."
FIREBASE_AUTH_DOMAIN="summersum-agent-dev.firebaseapp.com"
FIREBASE_PROJECT_ID="summersum-agent-dev"
FIREBASE_STORAGE_BUCKET="summersum-agent-dev.firebasestorage.app"
FIREBASE_MESSAGING_SENDER_ID="..."
FIREBASE_APP_ID="..."
```

### 2. Install Dependencies
Use `uv` to install all required packages:
```bash
uv sync
```

### 3. Extract Questions and Upload to GCS
To crop the questions from the PDFs, index them, and upload them to Google Cloud Storage:
```bash
uv run python scripts/upload_to_gcs.py
```
*This also renders the full pages from the PDF files and saves them to the cloud.*

### 4. Deploy Agent to Vertex AI
If the agent code (`app/agent.py`) is updated, deploy it to Vertex AI:
```bash
agents-cli deploy --project summersum-agent-dev --no-confirm-project --region us-east1
```
*This automatically updates the `deployment_metadata.json` file with the active cloud engine ID.*

### 5. Run Web Application Locally
Start the FastAPI server:
```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser to test the wiskundecoach!
