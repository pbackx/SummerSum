from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.tools import ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal
import os

# We keep EvaluationResult for any external schema dependencies
class EvaluationResult(BaseModel):
    is_correct: bool = Field(description="True if the student's solution is completely correct and verified, False otherwise")
    feedback: str = Field(description="Detailed, encouraging feedback in Dutch. If incorrect, explain where the mistake is without giving away the final answer. Give hints.")
    explanation: str = Field(description="Step-by-step clear explanation in Dutch of how to solve this question correctly.")

def mark_as_correct(tool_context: ToolContext) -> dict:
    """Marks the current math question as successfully solved by the student.
    
    Call this tool ONLY when you have evaluated the student's solution or answer 
    and verified that it is completely correct.
    """
    tool_context.state["status"] = "correct"
    return {"status": "success", "message": "Question marked as correct."}

async def inject_question_context(callback_context: CallbackContext, llm_request: LlmRequest) -> None:
    """Callback that prepends the question and correct solution images to the prompt using GCS URIs.
    
    This ensures that Gemini always sees the original question and the correct answer
    to verify the student's solution.
    """
    q_gcs_uri = callback_context.state.get("question_image_gcs")
    sol_gcs_uri = callback_context.state.get("solution_image_gcs")
    
    parts = []
    if q_gcs_uri:
        parts.append(types.Part.from_uri(file_uri=q_gcs_uri, mime_type="image/png"))
    if sol_gcs_uri:
        parts.append(types.Part.from_uri(file_uri=sol_gcs_uri, mime_type="image/png"))
        
    if parts and llm_request.contents:
        # Prepend the question and solution GCS image parts to the very first content block
        first_content = llm_request.contents[0]
        first_content.parts = parts + first_content.parts

# Define the evaluation/grading agent as a fallback/compatibility reference
evaluator_agent = Agent(
    name="math_evaluator",
    model="gemini-2.5-flash",
    instruction="Evaluate solutions and output JSON",
    output_schema=EvaluationResult
)

# Define the stateful math coach agent
math_coach_agent = Agent(
    name="math_coach",
    model="gemini-2.5-flash",
    instruction="""
    You are an encouraging and expert Dutch math coach. 
    Your goal is to help the student solve the math question shown in the question image.
    You also have access to the correct solution in the solution image.
    
    Current Question Context:
    - Question ID: {current_question_id}
    
    Pedagogical Guidelines:
    1. When the student asks for help, hints, or an explanation:
       - Explain the mathematical concepts involved clearly.
       - Provide hints or guide them through the next logical step.
       - DO NOT give the final answer or show the solution image.
       
    2. When the student submits a solution (text answer or a photo of their handwritten work):
       - Compare their solution step-by-step with the correct solution shown in the solution image.
       - If their solution is completely correct:
         - Congratulate them warmly in Dutch.
         - Tell them they are done for today ("Kom morgen terug!").
         - You MUST call the `mark_as_correct` tool.
       - If their solution is incorrect:
         - Point out exactly where the mistake is (e.g., sign error, wrong order of operations, arithmetic slip) but do not give the final correct answer.
         - Give encouraging hints to guide them to correct their mistake, and ask them to try again.
         - DO NOT show the solution image or reveal the final answer.
         
    Always speak in clear, patient, and warm Dutch.
    """,
    tools=[mark_as_correct],
    before_model_callback=inject_question_context
)

root_agent = math_coach_agent

app = App(
    root_agent=root_agent,
    name="app",
)
