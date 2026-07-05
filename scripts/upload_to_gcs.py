import os
import json
import fitz  # PyMuPDF
from PIL import Image
import io
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv

load_dotenv()

# Setup Firebase Admin
try:
    firebase_admin.get_app()
except ValueError:
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
    print(f"Initializing Firebase Admin with bucket: {bucket_name}")
    firebase_admin.initialize_app(options={
        'storageBucket': bucket_name
    })

db = firestore.client()
bucket = storage.bucket()

def upload_file_to_gcs(local_path, remote_path):
    print(f"Uploading {local_path} to gs://{bucket.name}/{remote_path}...")
    blob = bucket.blob(remote_path)
    blob.upload_from_filename(local_path)
    blob.make_public()
    return blob.public_url, f"gs://{bucket.name}/{remote_path}"

def render_full_pages():
    print("Rendering full page images from PDFs...")
    task_doc = fitz.open("Herhalingsbundel van 2 naar 3 vakantietaak.pdf")
    key_doc = fitz.open("Herhalingsbundel van 2 naar 3 vakantietaak correctiesleutel.pdf")

    # Mapped pages from extract_questions.py
    PAGE_MAPPING = {
        1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
        9: 9, 10: 10, 11: 11, 12: 12, 13: 13, 23: 14, 24: 15
    }

    rendered_files = {}
    for task_idx, key_idx in PAGE_MAPPING.items():
        page_num = task_idx + 1

        # 1. Render task page
        task_page = task_doc[task_idx]
        task_pix = task_page.get_pixmap(dpi=150)
        task_path = f"data/questions/page_{page_num}_task.png"
        task_pix.save(task_path)
        rendered_files[f"page_{page_num}_task"] = task_path

        # 2. Render key page
        if key_idx is not None:
            key_page = key_doc[key_idx]
            key_pix = key_page.get_pixmap(dpi=150)
            key_path = f"data/questions/page_{page_num}_key.png"
            key_pix.save(key_path)
            rendered_files[f"page_{page_num}_key"] = key_path

    print(f"Rendered {len(rendered_files)} full page images.")
    return rendered_files

def main():
    # 1. Render the full pages first
    rendered_pages = render_full_pages()

    # 2. Load database.json
    db_path = "data/database.json"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    with open(db_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Found {len(questions)} questions in database.json. Starting upload...")

    # 3. Cache uploads to avoid uploading duplicate files (like full pages used by multiple questions)
    uploaded_cache = {}

    def get_or_upload(local_path, remote_path):
        if not local_path:
            return None, None
        if local_path in uploaded_cache:
            return uploaded_cache[local_path]
        if not os.path.exists(local_path):
            print(f"Warning: File {local_path} does not exist.")
            return None, None
        url, gcs_uri = upload_file_to_gcs(local_path, remote_path)
        uploaded_cache[local_path] = (url, gcs_uri)
        return url, gcs_uri

    updated_questions = []
    for q in questions:
        q_id = q["id"]
        page_num = q["page"]

        # Upload cropped question image
        q_local = q["question_image"]
        q_remote = f"questions/question_{q_id}.png"
        q_url, q_gcs = get_or_upload(q_local, q_remote)

        # Upload cropped solution image
        sol_local = q["solution_image"]
        sol_remote = f"questions/solution_{q_id}.png"
        sol_url, sol_gcs = get_or_upload(sol_local, sol_remote)

        # Upload full task page
        task_page_local = f"data/questions/page_{page_num}_task.png"
        task_page_remote = f"pages/page_{page_num}_task.png"
        tp_url, tp_gcs = get_or_upload(task_page_local, task_page_remote)

        # Upload full key page
        key_page_local = f"data/questions/page_{page_num}_key.png"
        key_page_remote = f"pages/page_{page_num}_key.png"
        kp_url, kp_gcs = get_or_upload(key_page_local, key_page_remote)

        # Update database document values
        q["question_image_url"] = q_url
        q["question_image_gcs"] = q_gcs
        q["solution_image_url"] = sol_url
        q["solution_image_gcs"] = sol_gcs
        q["task_page_image_url"] = tp_url
        q["task_page_image_gcs"] = tp_gcs
        q["key_page_image_url"] = kp_url
        q["key_page_image_gcs"] = kp_gcs

        updated_questions.append(q)

        # Write to Firestore
        print(f"Updating Firestore document {q_id}...")
        db.collection("questions").document(q_id).set(q, merge=True)

    # Save back to database.json
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(updated_questions, f, indent=2, ensure_ascii=False)

    print("Migration successfully completed!")

if __name__ == "__main__":
    main()
