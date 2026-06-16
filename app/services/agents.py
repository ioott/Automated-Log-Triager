import logging
import json
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

logger = logging.getLogger(__name__)

class DiagnosticAgent:
    """
    AI Diagnostic Agent specialized in triaging transaction logs using RAG context.
    Orchestrated by CrewAI for enterprise-grade agentic workflows.
    Powered by Google Gemini for inference.
    """
    
    def __init__(self):
        if not settings.GOOGLE_API_KEY or settings.GOOGLE_API_KEY == "placeholder-key":
            raise ValueError("GOOGLE_API_KEY is not configured.")
        
        # Clean model name if necessary
        model_name = settings.GEMINI_MODEL_NAME.replace("models/", "") if settings.GEMINI_MODEL_NAME.startswith("models/") else settings.GEMINI_MODEL_NAME
        
        # Initialize Gemini LLM through LangChain
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0
        )
        
        # Define the specialized CrewAI Agent
        self.sre_advisor = Agent(
            role="Senior SRE & Diagnostic Specialist",
            goal="Provide clear, structured, and prioritized action plans for critical transaction failures.",
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
        Executes the AI diagnosis process using CrewAI orchestration.
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
            expected_output="A JSON object containing strictly these keys: root_cause, action_plan (list), risk_assessment, and advisor_notes.",
            agent=self.sre_advisor
        )

        crew = Crew(
            agents=[self.sre_advisor],
            tasks=[diagnosis_task],
            process=Process.sequential
        )

        try:
            logger.info("Kicking off CrewAI diagnosis process...")
            result = crew.kickoff()
            
            # CrewAI returns a CrewOutput object in newer versions, or a string.
            # We extract the raw string and parse the JSON.
            raw_output = result.raw if hasattr(result, "raw") else str(result)
            clean_result = raw_output.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_result)
        except Exception as e:
            logger.error(f"CrewAI Diagnosis failed: {str(e)}")
            raise e
