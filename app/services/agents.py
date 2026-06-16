import logging
import json
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

logger = logging.getLogger(__name__)

class DiagnosticAgent:
    """
    AI Diagnostic Agent specialized in triaging transaction logs using RAG context.
    Acts as a Senior SRE Advisor.
    """
    
    def __init__(self):
        # Initialize the LLM via LangChain (to be used by CrewAI)
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY
        )
        
        # Define the specialized Agent
        self.sre_advisor = Agent(
            role='Senior SRE & Diagnostic Specialist',
            goal='Provide clear, structured, and prioritized action plans for critical transaction failures.',
            backstory=(
                "You are an expert in fintech infrastructure and blockchain ledger systems. "
                "Your job is to analyze masked error logs alongside technical manual entries (RAG context). "
                "You output ONLY structured JSON advice to assist human operators."
            ),
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def run_diagnosis(self, masked_log: str, rag_context: str) -> dict:
        """
        Executes the AI diagnosis process using CrewAI.
        Includes a retry mechanism for robust LLM communication.
        """
        diagnosis_task = Task(
            description=(
                f"Analyze the following masked log:\n{masked_log}\n\n"
                f"Using the context from the technical manual:\n{rag_context}\n\n"
                "1. Identify the likely root cause based on the trace and RAG context.\n"
                "2. Propose a step-by-step action plan for the SRE team.\n"
                "3. Assess the immediate risk to the ecosystem (HIGH, MEDIUM, LOW).\n"
                "The output MUST be a valid JSON object."
            ),
            expected_output='A JSON object containing: root_cause, action_plan (list), risk_assessment, and advisor_notes.',
            agent=self.sre_advisor
        )

        crew = Crew(
            agents=[self.sre_advisor],
            tasks=[diagnosis_task],
            process=Process.sequential
        )

        result = crew.kickoff()
        
        # In a real async environment, CrewAI.kickoff() is synchronous. 
        # In a production FastAPI app, this should be wrapped in an executor if needed.
        # For simplicity in this pipeline, we process it as a result.
        
        try:
            # Attempt to parse the AI string output into JSON
            # Note: CrewAI output is an object, we need its 'raw' string or specific parsing
            return json.loads(result.raw)
        except Exception:
            # Fallback parsing if JSON is wrapped in code blocks
            clean_result = result.raw.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_result)
