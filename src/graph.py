from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from state import AgentState
from nodes import code_generator, code_runner, human_interrupt, qa_review_gate

max_try = 3

def decide_aft_exec(state: AgentState):
    if state.get("error") is None:
        return "qa_review_gate"
    elif state["iterations"] < max_try:
        return "code_generator"
    else:
        return "human_interrupt"

def decide_aft_qa(state: AgentState):
    if state.get("feedback") is None:
        return END
    else:
        return "code_generator"

gbldr = StateGraph(AgentState)

gbldr.add_node("code_generator", code_generator)
gbldr.add_node("code_runner", code_runner)
gbldr.add_node("human_interrupt", human_interrupt)
gbldr.add_node("qa_review_gate", qa_review_gate)

gbldr.add_edge(START, "code_generator")
gbldr.add_edge("code_generator", "code_runner")
gbldr.add_edge("human_interrupt", "code_generator")

gbldr.add_conditional_edges(
        "code_runner",
        decide_aft_exec, {
            "qa_review_gate": "qa_review_gate",
            "code_generator": "code_generator",
            "human_interrupt": "human_interrupt",
        }
    )

gbldr.add_conditional_edges(
        "qa_review_gate",
        decide_aft_qa, {
            END: END,
            "code_generator": "code_generator",
        }
    )

checkpoint = MemorySaver()
graph = gbldr.compile(checkpointer=checkpoint)