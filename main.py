# main.py
import os
import uuid
import sys
from openai import OpenAI, APIError

# Import our architectural primitives (100% unchanged!)
from schemas import ExpenseState, ExpenseAnalysis
from tools import get_company_policy

# Initialize the OpenAI Client
assert os.environ.get("OPENAI_API_KEY"), "Please export your OPENAI_API_KEY"
client = OpenAI()

class ExpenseOrchestrator:
    def __init__(self):
        self.db: dict[str, dict] = {}

    def ingest_new_receipt(self, receipt_text: str) -> str:
        tx_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
        state = ExpenseState(transaction_id=tx_id, raw_receipt_text=receipt_text)
        print(f"\n📥 [System] Ingested new transaction: {tx_id}")
        
        state = self._node_triage_and_evaluate(state)
        self.db[tx_id] = state.model_dump()
        return tx_id

    def _node_triage_and_evaluate(self, state: ExpenseState) -> ExpenseState:
        print(f"🤖 [Agent Node] Analyzing receipt text via OpenAI...")
        
        try:
            # Step A: Category extraction (Simulated RAG lookup)
            category_check = client.chat.completions.create(
                model="gpt-4o-mini", # Ultra-fast, cheap model perfect for orchestration
                messages=[
                    {"role": "user", "content": f"Extract only the category word (meal, flight, software_saas, other) from this text: {state.raw_receipt_text}"}
                ]
            )
            category = category_check.choices[0].message.content.strip().lower()
            policy_rule = get_company_policy(category)
            print(f"📖 [Tool Data Fetched] Applicable Policy: '{policy_rule}'")

            # Step B: Strict JSON structured enforcement using Pydantic
            prompt = (
                f"Analyze this receipt data: '{state.raw_receipt_text}'\n"
                f"Evaluate it strictly against this company policy: '{policy_rule}'"
            )
            
            response = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an automated triage layer. Evaluate expenses against policy rules."},
                    {"role": "user", "content": prompt}
                ],
                response_format=ExpenseAnalysis, # Strict architectural schema binding
                temperature=0.0
            )
            
            # OpenAI's parse framework automatically returns the parsed Pydantic object
            analysis = response.choices[0].message.parsed
            state.analysis = analysis
            
            # Programmatic routing based on the model's structured analysis
            if analysis.violates_policy:
                state.status = "awaiting_manager_approval"
                print("⚠️  [Routing decision] Policy violation detected. Route -> Freeze Thread for Human Review.")
            else:
                state.status = "auto_approved"
                print("✅ [Routing decision] Clean evaluation. Route -> Auto-Approve.")
                
        except APIError as e:
            print(f"\n❌ [Network Error] OpenAI API failed to respond.")
            print(f"   Details: Status {e.status_code} - {e.message}")
            state.status = "rejected" 
            state.reviewer_notes = f"System Error: OpenAI API failed with status {e.status_code}."
            self.db[state.transaction_id] = state.model_dump()
            sys.exit(0)
            
        except Exception as e:
            print(f"\n💥 [Application Error] System failure: {str(e)}")
            state.status = "rejected"
            self.db[state.transaction_id] = state.model_dump()
            sys.exit(0)
            
        return state

    def process_human_review(self, tx_id: str, approve: bool, notes: str):
        raw_data = self.db.get(tx_id)
        if not raw_data:
            print("Transaction not found.")
            return
            
        state = ExpenseState(**raw_data)
        state.reviewer_notes = notes
        
        if approve:
            state.status = "auto_approved"
            print(f"🚀 [System Finalized] Transaction {tx_id} approved. Dispatched to ERP.")
        else:
            state.status = "rejected"
            print(f"❌ [System Finalized] Transaction {tx_id} rejected.")
            
        self.db[tx_id] = state.model_dump()


# =====================================================================
# SIMULATION ENGINE
# =====================================================================
if __name__ == "__main__":
    orchestrator = ExpenseOrchestrator()
    
    # Run the exact same violating test payload
    mock_receipt = "Business Dinner at Capital Grille. Total: $124.50. Items: 2x Steaks, 1x Red Wine."
    
    tx_id = orchestrator.ingest_new_receipt(mock_receipt)
    current_snapshot = ExpenseState(**orchestrator.db[tx_id])
    
    print(f"\n--- Current Database Snapshot State ---")
    print(f"Status: {current_snapshot.status}")
    print(f"Details: Merchant: {current_snapshot.analysis.merchant}, Amount: ${current_snapshot.analysis.amount}")
    print(f"Justification: {current_snapshot.analysis.justification}")
    
    if current_snapshot.status == "awaiting_manager_approval":
        print("\n--- Human-in-the-Loop Intervention Triggered ---")
        user_input = input("This receipt broke policy. Force override approval? (yes/no): ")
        is_approved = user_input.strip().lower() == "yes"
        
        orchestrator.process_human_review(
            tx_id=tx_id, 
            approve=is_approved, 
            notes="Overriding because this was an executive client dinner meeting."
        )
