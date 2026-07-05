import os
import json
import fitz  # PyMuPDF
from PIL import Image
import io
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List

# Setup directories
os.makedirs("data/questions", exist_ok=True)

# Pydantic models for structured output from Gemini
class BoundingBox(BaseModel):
    # Coordinates normalized to 0-1000 representing [ymin, xmin, ymax, xmax]
    ymin: int
    xmin: int
    ymax: int
    xmax: int

class QuestionItem(BaseModel):
    id: str = Field(description="Unique sub-question ID like '1a', '1b', '2a', '3a'")
    question_box: BoundingBox = Field(description="Bounding box surrounding ONLY the question text/formula, excluding the student write-in area or solutions")
    solution_box: BoundingBox = Field(description="Bounding box surrounding the student write-in or solution area (where the answers appear in the correctiesleutel)")
    text_nl: str = Field(description="The Dutch text of the question (OCR/LaTeX format)")
    main_instruction: str = Field(description="The main instruction of this section (e.g., 'Werk uit.', 'Herleid volgende veeltermen.')")
    topic: str = Field(description="The math topic category of this question (e.g. 'Rationale getallen', 'Algebra', 'Hoeken')")
    difficulty: str = Field(description="Estimated difficulty level: 'easy', 'medium', 'hard'")

class PageAnalysis(BaseModel):
    page_number: int
    questions: List[QuestionItem]

# Hardcoded page mapping: vakantietaak.pdf index -> correctiesleutel.pdf index
# 0-based indexing
PAGE_MAPPING = {
    1: 1,   # p50
    2: 2,   # p51
    3: 3,   # p54
    4: 4,   # p55
    5: 5,   # p56
    6: 6,   # p57
    7: 7,   # p58
    8: 8,   # p59
    9: 9,   # p39
    10: 10, # p40
    11: 11, # p41
    12: 12, # p42
    13: 13, # p63
    23: 14, # p82
    24: 15  # p83
}

def analyze_page_with_gemini(client, page_img_bytes, page_num):
    print(f"Calling Gemini to analyze page {page_num}...")

    prompt = """
    Analyze this page from a 3rd-year math exercise book.
    Identify all individual sub-questions (like 1a, 1b, 2a, 3b, 10, 11a) on this page.
    For each sub-question, provide:
    1. A unique ID (e.g., '1a', '1b').
    2. A bounding box for the question itself (just the formula/text, no write-in lines). BE GENEROUS ON THE LEFT SIDE, ensuring letters like 'a', 'b', 'c' and minus signs are fully included.
    3. A bounding box for the solution/write-in area.
    4. The Dutch text of the question.
    5. The main instruction of this section (e.g., 'Werk uit.', 'Herleid volgende veeltermen.', 'Bereken.'). This is usually a heading or line of text above the question list.
    6. The math topic.
    7. An estimated difficulty ('easy', 'medium', 'hard').

    Coordinates must be integer values normalized to [0, 1000] where [0,0] is top-left and [1000, 1000] is bottom-right.
    """

    # Create Part from bytes
    image_part = types.Part.from_bytes(
        data=page_img_bytes,
        mime_type="image/png"
    )

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[image_part, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PageAnalysis,
            temperature=0.1
        ),
    )

    # Parse response text back to dict/Pydantic
    try:
        data = json.loads(response.text)
        return data
    except Exception as e:
        print(f"Failed to parse Gemini response for page {page_num}: {e}")
        print(response.text)
        return None

def get_overlap_area(r1, r2):
    if not r1 or not r2:
        return 0.0
    x_overlap = max(0.0, min(r1[2], r2[2]) - max(r1[0], r2[0]))
    y_overlap = max(0.0, min(r1[3], r2[3]) - max(r1[1], r2[1]))
    return x_overlap * y_overlap

def get_distance(r, box_pts):
    bx0, by0, bx1, by1 = r
    xmin, ymin, xmax, ymax = box_pts

    y_dist = 0.0
    if by1 < ymin:
        y_dist = ymin - by1
    elif by0 > ymax:
        y_dist = by0 - ymax

    x_dist = 0.0
    if bx1 < xmin:
        x_dist = xmin - bx1
    elif bx0 > xmax:
        x_dist = bx0 - xmax

    return x_dist, y_dist

def refine_box(page, box_norm, is_solution=False, other_box_norm=None):
    w_pts = page.rect.width
    h_pts = page.rect.height

    xmin = box_norm['xmin'] * w_pts / 1000.0
    ymin = box_norm['ymin'] * h_pts / 1000.0
    xmax = box_norm['xmax'] * w_pts / 1000.0
    ymax = box_norm['ymax'] * h_pts / 1000.0
    target_rect = (xmin, ymin, xmax, ymax)

    if other_box_norm:
        oxmin = other_box_norm['xmin'] * w_pts / 1000.0
        oymin = other_box_norm['ymin'] * h_pts / 1000.0
        oxmax = other_box_norm['xmax'] * w_pts / 1000.0
        oymax = other_box_norm['ymax'] * h_pts / 1000.0
        other_rect = (oxmin, oymin, oxmax, oymax)
    else:
        other_rect = None

    blocks = page.get_text("blocks")
    matching_blocks = []

    for b in blocks:
        bx0, by0, bx1, by1, btext, bnum, btype = b
        btext = btext.strip()
        if not btext:
            continue

        block_rect = (bx0, by0, bx1, by1)

        # Calculate overlap areas
        overlap_target = get_overlap_area(block_rect, target_rect)
        overlap_other = get_overlap_area(block_rect, other_rect) if other_rect else 0.0

        # Calculate distances
        x_dist_target, y_dist_target = get_distance(block_rect, target_rect)
        x_dist_other, y_dist_other = get_distance(block_rect, other_rect) if other_rect else (999.0, 999.0)

        # Is this block closer/more related to target_rect than other_rect?
        if other_rect:
            if overlap_other > overlap_target:
                continue
            if overlap_target == 0.0 and overlap_other == 0.0:
                dist_target = x_dist_target + y_dist_target
                dist_other = x_dist_other + y_dist_other
                if dist_other < dist_target:
                    continue

        # Apply thresholds to the target: vertical < 30, horizontal < 30
        if y_dist_target < 30 and x_dist_target < 30:
            matching_blocks.append(b)

    if matching_blocks:
        ux0 = min(b[0] for b in matching_blocks)
        uy0 = min(b[1] for b in matching_blocks)
        ux1 = max(b[2] for b in matching_blocks)
        uy1 = max(b[3] for b in matching_blocks)

        # Add padding in points
        if is_solution:
            pad_x = 5
            pad_y = 3
        else:
            pad_x = 10
            pad_y = 5

        ux0 = max(0.0, ux0 - pad_x)
        uy0 = max(0.0, uy0 - pad_y)
        ux1 = min(w_pts, ux1 + pad_x)
        uy1 = min(h_pts, uy1 + pad_y)

        return {"xmin": ux0, "ymin": uy0, "xmax": ux1, "ymax": uy1}
    else:
        # Fallback with generous padding
        if is_solution:
            pad_y = 15
            uy0 = max(0.0, ymin - pad_y)
            uy1 = min(h_pts, ymax + pad_y)
            return {"xmin": xmin, "ymin": uy0, "xmax": xmax, "ymax": uy1}
        else:
            pad_x_left = 15
            pad_x_right = 5
            pad_y = 5
            ux0 = max(0.0, xmin - pad_x_left)
            uy0 = max(0.0, ymin - pad_y)
            ux1 = min(w_pts, xmax + pad_x_right)
            uy1 = min(h_pts, ymax + pad_y)
            return {"xmin": ux0, "ymin": uy0, "xmax": ux1, "ymax": uy1}

def crop_and_save_pts(img, box_pts, output_path, scale=150.0/72.0):
    xmin = int(box_pts['xmin'] * scale)
    ymin = int(box_pts['ymin'] * scale)
    xmax = int(box_pts['xmax'] * scale)
    ymax = int(box_pts['ymax'] * scale)

    width, height = img.size

    if xmax <= xmin: xmax = min(xmin + 10, width)
    if ymax <= ymin: ymax = min(ymin + 10, height)

    xmin = max(0, min(xmin, width))
    xmax = max(0, min(xmax, width))
    ymin = max(0, min(ymin, height))
    ymax = max(0, min(ymax, height))

    cropped = img.crop((xmin, ymin, xmax, ymax))
    cropped.save(output_path)

def process_pdfs():
    # Initialize Google GenAI client using Vertex AI with ADC
    client = genai.Client(vertexai=True, project="summersum-agent-dev", location="us-central1")

    task_doc = fitz.open("Herhalingsbundel van 2 naar 3 vakantietaak.pdf")
    key_doc = fitz.open("Herhalingsbundel van 2 naar 3 vakantietaak correctiesleutel.pdf")

    db_path = "data/database.json"
    db_dict = {}
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    for item in existing_data:
                        if "id" in item:
                            db_dict[item["id"]] = item
        except Exception as e:
            print(f"Error loading existing database: {e}")

    # We process specific pages of interest (e.g., page 50 onwards)
    # You can change this to process all pages: sorted(PAGE_MAPPING.keys())
    pages_to_process = sorted(PAGE_MAPPING.keys())
    for task_idx in pages_to_process:
        # Determine which page has the visible solutions to send to Gemini
        key_idx = PAGE_MAPPING.get(task_idx)

        # Load the page we want to analyze with Gemini (preferably correctiesleutel where solutions are written)
        if key_idx is not None:
            analyze_page = key_doc[key_idx]
        else:
            analyze_page = task_doc[task_idx] # Fallback to task page where solutions are at the bottom

        analyze_pix = analyze_page.get_pixmap(dpi=150)
        analyze_img_data = analyze_pix.tobytes("png")

        # Call Gemini to get bounding boxes of questions and solutions on the ANALYZE page
        analysis = analyze_page_with_gemini(client, analyze_img_data, task_idx + 1)
        if not analysis or "questions" not in analysis:
            continue

        # Load task page (blank questions) for cropping questions
        task_page = task_doc[task_idx]
        task_pix = task_page.get_pixmap(dpi=150)
        task_img = Image.open(io.BytesIO(task_pix.tobytes("png")))

        # Load solution page (correctiesleutel or task page fallback) for cropping solutions
        if key_idx is not None:
            key_page = key_doc[key_idx]
            key_pix = key_page.get_pixmap(dpi=150)
            sol_img = Image.open(io.BytesIO(key_pix.tobytes("png")))
        else:
            sol_img = task_img # Fallback to same task page

        for q in analysis["questions"]:
            q_id = q["id"]
            db_id = f"p{task_idx + 1}_{q_id}"

            # Paths
            q_path = f"data/questions/question_{db_id}.png"
            sol_path = f"data/questions/solution_{db_id}.png"

            # Refine boxes using PDF text blocks
            refined_q_box = refine_box(task_page, q["question_box"], is_solution=False, other_box_norm=q["solution_box"])

            if key_idx is not None:
                refined_sol_box = refine_box(key_page, q["solution_box"], is_solution=True, other_box_norm=q["question_box"])
            else:
                refined_sol_box = refine_box(task_page, q["solution_box"], is_solution=True, other_box_norm=q["question_box"])

            # Crop question from the blank task PDF
            crop_and_save_pts(task_img, refined_q_box, q_path)

            # Crop solution from the solution PDF (where answers are written)
            crop_and_save_pts(sol_img, refined_sol_box, sol_path)

            db_dict[db_id] = {
                "id": db_id,
                "page": task_idx + 1,
                "question_id": q_id,
                "topic": q["topic"],
                "main_instruction": q["main_instruction"],
                "text_nl": q["text_nl"],
                "difficulty": q["difficulty"],
                "question_image": q_path,
                "solution_image": sol_path,
                "question_box": refined_q_box,
                "solution_box": refined_sol_box,
                "raw_question_box": q["question_box"],
                "raw_solution_box": q["solution_box"]
            }

            print(f"Processed question {db_id}")

    # Save database
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(list(db_dict.values()), f, indent=2, ensure_ascii=False)

    print(f"Finished preprocessing. Total database contains {len(db_dict)} questions.")

if __name__ == "__main__":
    process_pdfs()
