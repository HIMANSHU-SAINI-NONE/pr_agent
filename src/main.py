from dotenv import load_dotenv
load_dotenv()

import uuid
from langgraph.types import Command
from graph import graph

unique_thread_id =  str(uuid.uuid4())
config ={
            "configurable": {"thread_id": unique_thread_id},
            "tags": ["self-healing-agent", "cli-session"],
            "metadata": {"session_id": unique_thread_id}
        }

user_task = input("Enter the Python task/problem to solve: ").strip()

while not user_task:
    print("Task description cannot be empty.")
    user_task = input("Enter the Python task/problem to solve: ").strip()

init_state ={
                "task": user_task,
                "code": None,
                "error": None,
                "iterations": 0,
                "feedback": None
            }

print("Starting workflow on thread: " + unique_thread_id)
graph.invoke(init_state, config=config)

while True:
    snapshot = graph.get_state(config)

    if not snapshot.next:
        print("\n" + "=" * 70)
        print("[+] WORKFLOW COMPLETE: Pipeline terminated successfully at END.")
        print("=" * 70)
        print("Final Verified Implementation:\n")
        print(snapshot.values.get("code", "# [Warning] No code payload found in state."))
        print("=" * 70)
        break

    active_tasks = snapshot.tasks
    if not active_tasks or not active_tasks[0].interrupts:
        raise RuntimeError("Execution suspended, but no interrupt payload was surfaced by runtime.")

    interrupt_payload = active_tasks[0].interrupts[0].value

    if "error" in interrupt_payload:
        print("\n" + "!" * 70)
        print("[!] HITL ESCALATION GATE: Automated Repair Threshold Exceeded")
        print("!" * 70)
        print(f"Total Iterations Attempted : {interrupt_payload.get('attempts', 'N/A')}")
        print(f"Captured Traceback / Stderr:\n{interrupt_payload.get('error')}\n")
        print("Failing Candidate Code:")
        print("-" * 70)
        print(interrupt_payload.get("code", "# No code available."))
        print("-" * 70)

        human_hint = input("\nEnter directional guidance or debugging hint for the agent: ").strip()
        while not human_hint:
            print("[!] Input cannot be empty. Provide actionable instructions to unblock the agent.")
            human_hint = input("Enter directional guidance or debugging hint for the agent: ").strip()

        print("\n[*] Injecting developer feedback and resuming code generation cycle...")

        graph.invoke(Command(resume={"feedback": human_hint}), config=config)

    elif "passing_code" in interrupt_payload:
        print("\n" + "=" * 70)
        print("[?] QA VERIFICATION GATE: All Sandboxed Assertions Passed")
        print("=" * 70)
        print("Candidate Implementation for Review:")
        print("-" * 70)
        print(interrupt_payload.get("passing_code", "# No code available."))
        print("-" * 70)

        while True:
            decision = input("\nApprove candidate code for final delivery? (y/n): ").strip().lower()

            if decision in ["y", "yes", "n", "no"]:
                break
            print("[!] Invalid input. Please enter 'y' to approve or 'n' to reject.")

        if decision in ["y", "yes"]:
            print("\n[+] Verification confirmed. Finalizing workflow...")
            graph.invoke(Command(resume={"approved": True}), config=config)
        else:
            critique = input("Specify required architectural, styling, or logic modifications: ").strip()
            while not critique:
                print("[!] Rejection requires explicit change notes so the agent can patch the code.")
                critique = input("Specify required architectural, styling, or logic modifications: ").strip()

            print("\n[*] Routing reviewer critique back to code_generator for revision...")
            graph.invoke(Command(resume={"approved": False, "notes": critique}), config=config)

    else:
        raise ValueError(
            f"Encountered unrecognized interrupt payload schema: {interrupt_payload}. "
            "Verify that payload structures in nodes.py match the dispatch parser."
        )
    