document.addEventListener("DOMContentLoaded", async () => {
    const API_BASE = window.location.origin + "/api";

    // DOM Elements
    const chatMessages = document.getElementById("chat-messages");
    const chatForm = document.getElementById("chat-form");
    const textInput = document.getElementById("text-input");
    const fileUpload = document.getElementById("file-upload");
    const imagePreviewContainer = document.getElementById("image-preview-container");
    const imagePreview = document.getElementById("image-preview");
    const btnRemoveImage = document.getElementById("btn-remove-image");
    const btnNextQuestion = document.getElementById("btn-next-question");

    // Stats elements
    const streakVal = document.getElementById("streak-val");
    const progressPct = document.getElementById("progress-pct");
    const progressBar = document.getElementById("progress-bar");
    const solvedCount = document.getElementById("solved-count");
    const totalCount = document.getElementById("total-count");
    const topicsList = document.getElementById("topics-list");

    // Authentication DOM Elements
    const authOverlay = document.getElementById("auth-overlay");
    const authSubTitle = document.getElementById("auth-sub-title");
    const authErrorMsg = document.getElementById("auth-error-msg");
    const authErrorText = document.getElementById("auth-error-text");
    const btnLogout = document.getElementById("btn-logout");
    const userEmailDisplay = document.getElementById("user-email-display");
    const userProfileFooter = document.getElementById("user-profile-footer");
    const btnGoogleAuth = document.getElementById("btn-google-auth");
    const adminLinkContainer = document.getElementById("admin-link-container");

    let currentQuestion = null;
    let idToken = null;
    let auth = null;

    // Load initial stats & progress
    async function loadStats() {
        if (!idToken) return;
        try {
            const res = await fetch(`${API_BASE}/progress`, {
                headers: { "Authorization": `Bearer ${idToken}` }
            });
            if (!res.ok) throw new Error("Failed to load statistics.");
            const data = await res.json();

            // Update UI
            streakVal.textContent = data.streak;
            solvedCount.textContent = data.correct;
            totalCount.textContent = data.total_questions;

            const pct = data.total_questions > 0 ? Math.round((data.completed / data.total_questions) * 100) : 0;
            progressPct.textContent = `${pct}%`;

            // Progress ring dashoffset calculation (r=50, circumference = 2 * PI * r = 314.15)
            const circumference = 314.15;
            const offset = circumference - (pct / 100) * circumference;
            progressBar.style.strokeDashoffset = offset;

            // Load topics list
            topicsList.innerHTML = "";
            for (const [name, stats] of Object.entries(data.topics)) {
                const topicPct = stats.total > 0 ? Math.round((stats.correct / stats.total) * 100) : 0;

                const row = document.createElement("div");
                row.className = "topic-row";
                row.innerHTML = `
                    <div class="topic-info">
                        <span class="topic-name" title="${name}">${name}</span>
                        <span class="topic-count">${stats.correct}/${stats.total}</span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: ${topicPct}%"></div>
                    </div>
                `;
                topicsList.appendChild(row);
            }
        } catch (err) {
            console.error("Failed to load progress stats:", err);
        }
    }

    // Helper to render math using KaTeX
    function renderMath(element) {
        if (window.renderMathInElement) {
            window.renderMathInElement(element, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false},
                    {left: "\\(", right: "\\)", display: false},
                    {left: "\\[", right: "\\]", display: true}
                ],
                throwOnError: false
            });
        } else {
            // Retry if KaTeX deferred script hasn't finished loading
            setTimeout(() => renderMath(element), 100);
        }
    }

    // Append a message to the chat window
    function appendMessage(sender, content, mediaUrl = null, extraHtml = "") {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${sender}`;

        let html = "";
        if (mediaUrl) {
            html += `<img src="${mediaUrl}" class="question-img" alt="Wiskunde Vraag">`;
        }
        html += `<div class="message-text">${content}</div>`;
        if (extraHtml) {
            html += extraHtml;
        }

        msgDiv.innerHTML = html;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Render math equations with KaTeX
        renderMath(msgDiv);

        return msgDiv;
    }

    // Load next question from the API
    async function fetchNextQuestion() {
        if (!idToken) return;

        const hintsContainer = document.getElementById("hints-container");
        if (hintsContainer) {
            hintsContainer.classList.add("hidden");
        }

        // Show status
        appendMessage("system-msg", "Coach zoekt een passende som voor je op...");

        try {
            const res = await fetch(`${API_BASE}/next_question`, {
                headers: { "Authorization": `Bearer ${idToken}` }
            });
            if (!res.ok) throw new Error("Backend is offline or database empty.");
            const question = await res.json();
            currentQuestion = question;

            if (hintsContainer) {
                hintsContainer.classList.remove("hidden");
            }

            // Construct the path to serve the image (from GCS public URL or local fallback)
            const questionImageUrl = question.question_image_url || `${window.location.origin}/${question.question_image}`;

            const extra = `
                <div class="question-msg-content">
                    <span class="badge badge-${question.difficulty}">${question.difficulty}</span>
                    <p><em>Onderwerp: ${question.topic}</em></p>
                </div>
            `;

            const taskText = question.main_instruction ? `<strong>Opdracht: ${question.main_instruction}</strong><br><br>` : "";

            appendMessage(
                "coach",
                `Hier is de wiskundevraag voor vandaag:<br><br>${taskText}<strong>"${question.text_nl}"</strong>. Los het op, schrijf je berekening op papier en stuur me een foto!`,
                questionImageUrl,
                extra
            );
        } catch (err) {
            appendMessage("coach", "Oeps, er ging iets fout bij het ophalen van de vraag. Zorg ervoor dat het extractie-script succesvol is gedraaid en de backend live is.");
            console.error(err);
        }
    }

    // Remove image preview
    btnRemoveImage.addEventListener("click", () => {
        fileUpload.value = "";
        imagePreviewContainer.classList.add("hidden");
    });

    // Image upload preview
    fileUpload.addEventListener("change", () => {
        const file = fileUpload.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                imagePreviewContainer.classList.remove("hidden");
            };
            reader.readAsDataURL(file);
        }
    });

    // Handle submit
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!idToken) return;

        const text = textInput.value.trim();
        const file = fileUpload.files[0];

        if (!text && !file) return;
        if (!currentQuestion) {
            appendMessage("coach", "Vraag eerst een som aan met de knop 'Nieuwe Som'!");
            return;
        }

        // Show student message in chat
        let mediaUrl = null;
        if (file) {
            mediaUrl = URL.createObjectURL(file);
        }

        appendMessage("student", text || "Hier is mijn uitwerking op foto:", mediaUrl);

        // Reset inputs
        textInput.value = "";
        fileUpload.value = "";
        imagePreviewContainer.classList.add("hidden");

        // Loading state
        const loadingDiv = appendMessage("system-msg", "Coach beoordeelt jouw oplossing. Even geduld...");

        // Prepare multipart form data
        const formData = new FormData();
        formData.append("question_id", currentQuestion.id);
        if (text) formData.append("student_answer_text", text);
        if (file) formData.append("student_answer_file", file);

        try {
            const res = await fetch(`${API_BASE}/submit`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${idToken}` },
                body: formData
            });

            if (!res.ok) throw new Error("Failed to submit solution.");
            const data = await res.json();

            // Remove loading indicator
            loadingDiv.remove();

            const gradeClass = data.is_correct ? "correct-panel" : "incorrect-panel";
            const gradeTextClass = data.is_correct ? "correct-text" : "incorrect-text";
            const gradeIcon = data.is_correct ? "fa-circle-check" : "fa-circle-xmark";
            const gradeTitle = data.is_correct ? "Goed gedaan!" : "Niet helemaal juist";

            // Accordion for solution/explanation
            const expId = `exp-${Date.now()}`;
            const extraHtml = `
                <div class="grade-panel ${gradeClass}">
                    <div class="grade-header ${gradeTextClass}">
                        <i class="fa-solid ${gradeIcon}"></i>
                        <span>${gradeTitle}</span>
                    </div>
                    <p>${data.feedback}</p>

                    <div class="explanation-accordion">
                        <button class="explanation-trigger" onclick="document.getElementById('${expId}').classList.toggle('hidden'); this.classList.toggle('active')">
                            <i class="fa-solid fa-chevron-down"></i> Bekijk stapsgewijze uitleg
                        </button>
                        <div id="${expId}" class="explanation-content hidden">
                            <p>${data.explanation}</p>
                            <h4 style="margin: 8px 0 4px 0;">Correcte Oplossing:</h4>
                            <img src="${currentQuestion.solution_image_url || `${window.location.origin}/${currentQuestion.solution_image}`}" class="solution-img" alt="Oplossing">
                        </div>
                    </div>
                </div>
            `;

            appendMessage("coach", data.is_correct ? "Super! Je antwoord is helemaal correct." : "Ik heb je uitwerking nagekeken. Kijk eens hieronder naar de feedback en de uitleg om je te helpen:", null, extraHtml);

            // Reload stats & progress
            loadStats();

            if (data.is_correct) {
                currentQuestion = null; // Reset current question after correct solve
                const hintsContainer = document.getElementById("hints-container");
                if (hintsContainer) {
                    hintsContainer.classList.add("hidden");
                }
            }
        } catch (err) {
            loadingDiv.remove();
            appendMessage("coach", "Er ging iets mis bij het beoordelen van je antwoord. Probeer het opnieuw.");
            console.error(err);
        }
    });

    btnNextQuestion.addEventListener("click", fetchNextQuestion);

    // Initial Firebase Config Fetch and Auth Initialization
    async function initializeApp() {
        try {
            const configRes = await fetch(`${API_BASE}/config`);
            if (!configRes.ok) throw new Error("Could not fetch Firebase configuration from backend API.");
            const firebaseConfig = await configRes.json();

            if (!firebaseConfig.apiKey) {
                // Config variables not filled in yet in .env
                appendMessage("coach", "<strong>Configuratiefout:</strong> Firebase API sleutels missen in het <code>.env</code>-bestand van de backend. Vul deze in om in te loggen.");
                authOverlay.innerHTML = `
                    <div class="auth-card" style="text-align: center;">
                        <i class="fa-solid fa-circle-exclamation" style="font-size: 48px; color: var(--incorrect);"></i>
                        <h2 style="margin-top: 16px;">Configuratiefout</h2>
                        <p style="margin-top: 12px; line-height: 1.5; color: var(--text-muted);">De Firebase API-keys zijn nog niet geconfigureerd in het backend <code>.env</code>-bestand.<br><br>Vul deze in en herstart de server om in te kunnen loggen.</p>
                    </div>
                `;
                return;
            }

            // Initialize Firebase SDK
            firebase.initializeApp(firebaseConfig);
            auth = firebase.auth();

            // Listen to auth state changes
            auth.onAuthStateChanged(async (user) => {
                if (user) {
                    idToken = await user.getIdToken();

                    // Show dashboard
                    userEmailDisplay.textContent = user.email;
                    userProfileFooter.classList.remove("hidden");
                    authOverlay.classList.add("hidden");

                    // Toggle admin panel access link
                    if (user.email === "peter.backx@gmail.com") {
                        if (adminLinkContainer) adminLinkContainer.classList.remove("hidden");
                    } else {
                        if (adminLinkContainer) adminLinkContainer.classList.add("hidden");
                    }

                    // Load statistics
                    loadStats();
                } else {
                    idToken = null;
                    userProfileFooter.classList.add("hidden");
                    authOverlay.classList.remove("hidden");
                    if (adminLinkContainer) adminLinkContainer.classList.add("hidden");
                    const hintsContainer = document.getElementById("hints-container");
                    if (hintsContainer) hintsContainer.classList.add("hidden");

                    // Reset stats views
                    streakVal.textContent = "0";
                    solvedCount.textContent = "0";
                    totalCount.textContent = "0";
                    progressPct.textContent = "0%";
                    progressBar.style.strokeDashoffset = "314.15";
                    topicsList.innerHTML = `
                        <div class="topic-skeleton"></div>
                        <div class="topic-skeleton"></div>
                        <div class="topic-skeleton"></div>
                    `;
                }
            });

            // Google Sign-In button listener
            if (btnGoogleAuth) {
                btnGoogleAuth.addEventListener("click", async () => {
                    authErrorMsg.classList.add("hidden");
                    btnGoogleAuth.disabled = true;
                    try {
                        const provider = new firebase.auth.GoogleAuthProvider();
                        await auth.signInWithPopup(provider);
                    } catch (err) {
                        console.error(err);
                        let msg = err.message;
                        if (err.code === "auth/popup-closed-by-user") {
                            msg = "Inloggen geannuleerd.";
                        }
                        authErrorText.textContent = msg;
                        authErrorMsg.classList.remove("hidden");
                    } finally {
                        btnGoogleAuth.disabled = false;
                    }
                });
            }

            // Logout button
            btnLogout.addEventListener("click", () => {
                auth.signOut();
            });

        } catch (err) {
            console.error("Firebase Auth Init Failed:", err);
            appendMessage("coach", "Fout bij laden authenticatie. Controleer netwerkverbinding.");
        }
    }

    // Hint buttons click handlers
    const hintsContainer = document.getElementById("hints-container");
    if (hintsContainer) {
        hintsContainer.addEventListener("click", async (e) => {
            const btn = e.target.closest(".btn-hint");
            if (!btn || !currentQuestion || !idToken) return;

            const hintType = btn.getAttribute("data-hint");
            let promptText = "";
            let chatText = "";

            if (hintType === "klein") {
                promptText = "Ik wil graag een kleine hint voor deze som.";
                chatText = "💡 Ik wil graag een kleine hint.";
            } else if (hintType === "formule") {
                promptText = "Welke wiskunderegel of formule hoort bij deze som?";
                chatText = "📘 Welke wiskunderegel of formule hoort hierbij?";
            } else if (hintType === "voorbeeld") {
                promptText = "Geef me een soortgelijk voorbeeld met de uitwerking.";
                chatText = "🔍 Kun je me een vergelijkbaar voorbeeld geven?";
            }

            if (!promptText) return;

            // Show student message in chat
            appendMessage("student", chatText);

            // Loading state
            const loadingDiv = appendMessage("system-msg", "Coach typt een hint...");

            // Disable input/buttons during request
            const btnSubmit = document.getElementById("btn-submit");
            btnSubmit.disabled = true;
            textInput.disabled = true;

            // Submit to backend
            const formData = new FormData();
            formData.append("question_id", currentQuestion.id);
            formData.append("student_answer_text", promptText);

            try {
                const res = await fetch(`${API_BASE}/submit`, {
                    method: "POST",
                    headers: { "Authorization": `Bearer ${idToken}` },
                    body: formData
                });

                if (!res.ok) throw new Error("Failed to get hint.");
                const data = await res.json();

                loadingDiv.remove();

                // Show coach hint response
                appendMessage("coach", data.feedback);

            } catch (err) {
                loadingDiv.remove();
                appendMessage("coach", "Er ging iets mis bij het ophalen van de hint. Probeer het opnieuw.");
                console.error(err);
            } finally {
                btnSubmit.disabled = false;
                textInput.disabled = false;
            }
        });
    }

    // Run initial load & setup
    initializeApp();
});
