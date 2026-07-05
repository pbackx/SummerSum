# Capstone Project Submission: SummerSum

This document serves as the project report and resources repository for the Kaggle Capstone Project submission in the **Agents for Good** category.

---

## 🏆 Project Identity

* **Track:** Agents for Good (Education)
* **Title:** **SummerSum: Preventing the "Summer Slide" with a Multimodal AI Math Coach**
* **Subtitle:** An interactive web application and Vertex-deployed AI agent that provides stateful, didactic math coaching to secondary school students by analyzing handwritten calculations directly from photos.
* **Public Repository:** [GitHub Repository (Local Workspace)](file:///c:/dev/SummerSum)

---

## 📝 Project Description

### 1. The Challenge: The "Summer Slide" & The Transition Bottleneck
During the long summer break, secondary school students often experience a significant drop in academic skills, commonly known as the **"Summer Slide"**. In mathematics, this effect is particularly severe. As students transition from the 2nd to the 3rd year of secondary school, math concepts shift from basic arithmetic to abstract algebra, geometry, and rational functions.

Traditional exercise books are static. They either provide a simple correction key (which allows cheating or reveals answers too quickly) or no feedback at all. When students get stuck, they experience frustration and give up. Private tutoring is highly effective but financially out of reach for many families. There is a critical need for an accessible, stateful, and interactive helper that acts like a real tutor.

### 2. The Solution: SummerSum Math Coach
**SummerSum** is an interactive, mobile-friendly web application designed to help secondary school students practice math daily during the summer holidays. Instead of replacing teachers, SummerSum democratizes tutoring by offering a personal AI math coach on every student's smartphone.

#### Key Features:
* **Bite-Sized Daily Practice:** Students receive exactly one math question per day tailored to their progress, preventing burnout while building a daily habit.
* **Handwritten Work Upload (Multimodal):** Math is written on paper, not typed. Students write down their calculations, take a photo, and upload it. The agent reads the handwriting and guides them.
* **Active Didactic Tutoring:** Powered by Google's Agent Development Kit (ADK) and Vertex AI Agent Runtime. The AI coach acts as a Socratic tutor—pointing out sign mistakes, offering conceptual hints, or providing similar step-by-step examples without revealing the final answer.
* **Gamification & Engagement:** A daily streak tracker keeps students motivated to log in every day.
* **Admin Dashboard:** A secure administrative portal for teachers to audit user progress, view questions, and edit cropping boundaries.

### 3. Under the Hood: Technical Architecture & Key Decisions

SummerSum's architecture showcases how advanced Google Enterprise Agent technologies can power consumer-facing education apps:

1. **Automated Content Pipeline:**
   We built an automated script (`scripts/extract_questions.py`) using `gemini-2.5-flash` as a layout parser. It automatically reads PDF exercise books, detects sub-questions (e.g., `1a`, `1b`), draws bounding boxes around questions and answers, and uploads cropped PNGs to **Google Cloud Storage** while saving metadata in **Cloud Firestore**.
2. **Stateful Vertex AI Reasoning Engine:**
   Instead of stateless API calls, our math coach is implemented via the **Google ADK** and deployed to **Vertex AI Agent Runtime (Reasoning Engine)**. This keeps the conversation state in the cloud. The FastAPI backend streams the model's responses to the user.
3. **Multimodal Analysis Callback:**
   We use an ADK `before_model_callback` (`inject_question_context`) that automatically prepends the GCS URIs of the original question and the correct solution sheet to the LLM context. This allows Gemini to compare the student's handwritten work with the correct answer key on the fly.
4. **Tool-Driven State Progression:**
   When the math coach verifies that the student's answer is 100% correct, it calls the `mark_as_correct` tool. The backend detects this tool execution to increment the student's streak and unlock the step-by-step solution accordion.
5. **Secure Firebase Authentication:**
   A streamlined "Continue with Google" sign-in removes signup friction. Strict JWT-based verification ensures only authorized administrators can view user data and edit questions.

---

## 🎬 Video Script (3-Minute Presentation)

* **Goal:** A clear, engaging, and professional pitch of SummerSum, covering the problem, why AI agents are the solution, our architecture, a short demo, and our deployment.
* **Target Duration:** ~3 minutes (approx. 420 words)
* **Tone:** Enthusiastic, educational, and tech-forward.

| Time | Visual cue | Narration / Voiceover |
| :--- | :--- | :--- |
| **0:00 - 0:25** | **[Visual: Close-up of a student looking frustrated at a math textbook, followed by a graphic of the "Summer Slide" learning curve going down.]** | "Every summer, millions of secondary school students experience the 'summer slide'—losing critical math skills over the long holidays. As they transition to higher grades, math becomes abstract and challenging. Static textbooks and answer sheets fail them: they either give away the answer immediately, or leave students stuck and frustrated. And private tutoring is a luxury most families cannot afford." |
| **0:25 - 0:55** | **[Visual: Cut to a beautiful, clean mobile phone screen showing the SummerSum app. The user logs in with one click via 'Continue with Google', revealing the 'Question of the Day'.]** | "Introducing **SummerSum**, a personal AI math coach designed to keep students engaged and learning. SummerSum combines a bite-sized daily practice interface with a stateful AI coach. Students log in, get one tailored math question, write their solution on paper, and upload a photo. No complex LaTeX typing required—just pen, paper, and a smartphone." |
| **0:55 - 1:30** | **[Visual: Screen recording showing a user uploading a photo of a handwritten math problem with a small sign error. The AI Coach responds in Dutch with LaTeX rendering: 'Goed geprobeerd! Let goed op het minteken bij de haakjes...']** | "What makes SummerSum unique is that the agent acts as a true didactic coach. Instead of revealing the solution, it analyzes the student's handwritten work, points out specific errors like sign slips or order of operations, and asks guiding hints. It can provide formulas, general hints, or even generate similar step-by-step examples on the fly." |
| **1:30 - 2:10** | **[Visual: Dynamic architecture diagram showing: Frontend -> FastAPI -> Vertex AI Reasoning Engine -> Google Cloud Storage & Cloud Firestore.]** | "Behind the scenes, SummerSum is built on a robust enterprise stack. We created an automated pipeline using `gemini-2.5-flash` to parse textbook PDFs, crop questions, and store them in Google Cloud Storage. The AI math coach is built with the Google Agent Development Kit and deployed to **Vertex AI Agent Runtime** as a Reasoning Engine, maintaining conversation states across sessions." |
| **2:10 - 2:40** | **[Visual: Show the admin panel. Peter logs in, views the user progress table, and reviews question bounding boxes.]** | "When a student successfully solves a problem, the agent calls our `mark_as_correct` tool. This triggers a Firestore update, increases the student's daily streak to boost motivation, and unlocks the official step-by-step solution. Security is baked in: the application uses Firebase Auth, protecting the database and admin dashboard from unauthorized access." |
| **2:40 - 3:00** | **[Visual: Show a happy student completing a streak. The screen displays '3-day streak!'. Fade out to the logo and links.]** | "By putting state-of-the-art multimodal AI in the hands of every student, SummerSum turns screen time into learning time. It prevents learning loss, builds confidence, and makes quality tutoring accessible to all. SummerSum—your personal math coach, anytime, anywhere. Thank you." |

---

## 🛠️ Verification & Resource Mapping

Here are the key files and references that back up this writeup:

* **Agent Definition & Prompts:** [app/agent.py](file:///c:/dev/SummerSum/app/agent.py)
* **API Endpoints & Orchestration:** [app/main.py](file:///c:/dev/SummerSum/app/main.py)
* **Automated Layout Parsing Script:** [scripts/extract_questions.py](file:///c:/dev/SummerSum/scripts/extract_questions.py)
* **Database & Migrations Schema:** [app/firebase_db.py](file:///c:/dev/SummerSum/app/firebase_db.py)
* **Frontend Application Code:** [frontend/app.js](file:///c:/dev/SummerSum/frontend/app.js)
