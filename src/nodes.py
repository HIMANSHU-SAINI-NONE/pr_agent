from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.types import interrupt

from executor import execute_pycode
from schema import code_base
from state import AgentState

load_dotenv()

model = init_chat_model(
    "gemini-3.5-flash-lite",
    model_provider="google_genai",
    temperature=0
)

struct_regulator = model.with_structured_output(code_base)

def code_generator(state: AgentState) -> dict:
    """
    Generates or patches code using model and previous code, error code and human feedback inputs
    """
    task = state["task"]
    current_code = state.get("code")
    last_error = state.get("error")
    feedback = state.get("feedback")

    if last_error:
        system_prompt = (
            f"You are a self-healing Python assistant.\n"
            f"Original Task: {task}\n\n"
            f"Your previous attempt produced an error:\n{last_error}\n\n"
            f"Previous Code:\n{current_code}\n\n"
        )
        if feedback:
            system_prompt += f"Human guidance/hint: {feedback}\n\n"
        system_prompt += "Fix the bugs and return corrected, runnable Python code with assertions."
    elif feedback:
        system_prompt = (
            f"Original Task: {task}\n\n"
            f"The code passed unit tests, but the human reviewer requested changes:\n{feedback}\n\n"
            f"Previous Code:\n{current_code}\n\n"
            "Update the code to satisfy the reviewer's instructions while keeping assertions working."
        )
    else:
        system_prompt = (
            f"Write a complete, clean Python solution for the following task:\n{task}\n\n"
            "Include self-contained `assert` statements at the bottom of the script "
            "to rigorously test the solution and common edge cases."
        )

    response = struct_regulator.invoke(system_prompt)

    return {
        "code": response.code,
        "iterations": state.get("iterations", 0) + 1,
        "error": None,           
        "feedback": None   
    }

def code_runner(state: AgentState) -> dict:
    """
    Executes the generated code and returns any error messages
    """
    code = state["code"]

    success, error_msg = execute_pycode(code)

    return {
        "error": error_msg if not success else None
    }

def human_interrupt(state: AgentState) -> dict:
    payload = {
        "message": "Max retry limit reached. Agent needs guidance.",
        "code": state["code"],
        "error": state["error"],
        "attempts": state["iterations"],
    }

    human_response = interrupt(payload)

    # Defensively extract text whether Studio sends a dict or raw text
    if isinstance(human_response, dict):
        hint = human_response.get("feedback", "")
    else:
        hint = str(human_response).strip()

    return {
        "feedback": hint,
        "iterations": 0,
    }

def qa_review_gate(state: AgentState) -> dict:
    """
    HITL Gate 2: Halts graph after automated tests pass to get human approval.
    Supports both Studio CLI strings ('y', 'yes', 'approve') and dict payloads.
    """
    payload = {
        "message": "All tests passed. Please review the final code for sign-off.",
        "passing_code": state["code"]
    }

    review = interrupt(payload)

    # 1. Determine if the input represents approval
    is_approved = False

    if isinstance(review, dict):
        is_approved = review.get("approved") is True
    elif isinstance(review, str):
        clean_text = review.strip().lower()
        if clean_text in ["y", "yes", "approved", "approve", "true"]:
            is_approved = True

    # 2. Return appropriate state update
    if is_approved:
        # Approval clears feedback so decide_aft_qa routes to END
        return {"feedback": None}
    else:
        # Rejection captures review notes to guide code_generator
        if isinstance(review, dict):
            notes = review.get("notes", "Changes requested by reviewer.")
        else:
            notes = str(review) if str(review).strip() not in ["n", "no"] else "Rejected without specific notes."

        return {"feedback": notes}
    