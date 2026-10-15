# main.py
import os
import uuid
from google import genai
from google.genai import types
import time
from google.genai.errors import ServerError
import sys
from google.genai.errors import APIError

# Import our architectural primitives
from schemas import ExpenseState, ExpenseAnalysis
from tools import get_company_policy

# Initialize the Gemini Client (Reads GEMINI_API_KEY from environment)
assert os.environ.get("GEMINI_API_KEY"), "Please export your GEMINI_API_KEY"
client = genai.Client()

class ExpenseOrchestrator:
    def __init__(self):
        # Mock database to store our serialized state snapshots
        self.db: dict[str, dict] = {}

    def ingest_new_receipt(self, receipt_text: str) -> str:
        """Step 1: Ingest payload and create a fresh state machine snapshot."""
        tx_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
        state = ExpenseState(transaction_id=tx_id, raw_receipt_text=receipt_text)
        
        print(f"\n📥 [System] Ingested new transaction: {tx_id}")
        
        # Run Triage Node
        state = self._node_triage_and_evaluate(state)
        
        # Dehydrate/Save to DB
        self.db[tx_id] = state.model_dump()
        return tx_id

    def _node_triage_and_evaluate(self, state: ExpenseState) -> ExpenseState:
        """The core agentic node. Combines RAG tools with Structured Outputs."""
        print(f"🤖 [Agent Node] Analyzing receipt text...")
        
        try:
            # Step A: Category extraction (Simulated RAG lookup)
            category_check = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"Extract only the category word (meal, flight, software_saas, other) from this text: {state.raw_receipt_text}"
            )
            category = category_check.text.strip().lower()
            policy_rule = get_company_policy(category)
            print(f"📖 [Tool Data Fetched] Applicable Policy: '{policy_rule}'")

            # Step B: Strict JSON structured enforcement
            prompt = (
                f"Analyze this receipt data: '{state.raw_receipt_text}'\n"
                f"Evaluate it strictly against this company policy: '{policy_rule}'"
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExpenseAnalysis, 
                    temperature=0.0
                )
            )
            
            # Hydrate JSON to Pydantic object
            analysis = ExpenseAnalysis.model_validate_json(response.text)
            state.analysis = analysis
            
            # Determine programmatic routing
            if analysis.violates_policy:
                state.status = "awaiting_manager_approval"
                print("⚠️  [Routing decision] Policy violation detected. Route -> Freeze Thread for Human Review.")
            else:
                state.status = "auto_approved"
                print("✅ [Routing decision] Clean evaluation. Route -> Auto-Approve.")
                
        except APIError as e:
            # Graceful handling for 503, 429, or authentication errors
            print(f"\n❌ [Network Error] The upstream LLM provider failed to respond.")
            print(f"   Details: Code {e.code} - {e.message}")
            print("   Action: Transaction state frozen. Aborting execution thread cleanly.")
            
            # Update our persistent state so the database reflects the system failure
            state.status = "rejected" 
            state.reviewer_notes = f"System Error: Upstream AI API failed with status {e.code}."
            
            # Gracefully exit the script execution without exploding the console stack trace
            self.db[state.transaction_id] = state.model_dump()
            sys.exit(0)
            
        except Exception as e:
            # Catch-all for unexpected serialization or validation bugs
            print(f"\n💥 [Application Error] An unexpected system failure occurred: {str(e)}")
            state.status = "rejected"
            self.db[state.transaction_id] = state.model_dump()
            sys.exit(0)
            
        return state

    def process_human_review(self, tx_id: str, approve: bool, notes: str):
        """Step 2: Re-entry gateway. Hydrates state from DB and processes human input."""
        raw_data = self.db.get(tx_id)
        if not raw_data:
            print("Transaction not found.")
            return
            
        state = ExpenseState(**raw_data)
        state.reviewer_notes = notes
        
        if approve:
            state.status = "auto_approved"
            print(f"🚀 [System Finalized] Transaction {tx_id} approved by manager. Dispatched to ERP payroll system.")
        else:
            state.status = "rejected"
            print(f"❌ [System Finalized] Transaction {tx_id} formally rejected. Sent back to employee.")
            
        self.db[tx_id] = state.model_dump()


# =====================================================================
# SIMULATION ENGINE
# =====================================================================
if __name__ == "__main__":
    orchestrator = ExpenseOrchestrator()
    
    # Test Scenario: A meal receipt that violates the $75 limit policy rule
    mock_receipt = "Business Dinner at Capital Grille. Total: $124.50. Items: 2x Steaks, 1x Red Wine."
    
    tx_id = orchestrator.ingest_new_receipt(mock_receipt)
    
    # Check the database snapshot status
    current_snapshot = ExpenseState(**orchestrator.db[tx_id])
    print(f"\n--- Current Database Snapshot State ---")
    print(f"Status: {current_snapshot.status}")
    print(f"Extract Details: Merchant: {current_snapshot.analysis.merchant}, Amount: ${current_snapshot.analysis.amount}")
    print(f"Justification: {current_snapshot.analysis.justification}")
    
    # Simulate a human popping open a UI and hitting the approval re-entry route later
    if current_snapshot.status == "awaiting_manager_approval":
        print("\n--- Human-in-the-Loop Intervention Triggered ---")
        user_input = input("This receipt broke policy. Force override approval? (yes/no): ")
        is_approved = user_input.strip().lower() == "yes"
        
        orchestrator.process_human_review(
            tx_id=tx_id, 
            approve=is_approved, 
            notes="Overriding because this was an executive client dinner meeting."
        )
