import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

logger = logging.getLogger(__name__)

class DiagnosticAgent:
    """
    AI Diagnostic Agent specialized in triaging transaction logs using RAG context.
    Built with LangChain for high performance and lightweight build times.
    """
    
    def __init__(self):
        self._llm = None
        self._chain = None
        self.parser = JsonOutputParser()
        
    @property
    def chain(self):
        if self._chain is None:
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sk-placeholder":
                raise ValueError("OPENAI_API_KEY is not configured. Please set it in the .env file.")
            
            self._llm = ChatOpenAI(
                model=settings.OPENAI_MODEL_NAME,
                api_key=settings.OPENAI_API_KEY,
                temperature=0
            )
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "You are a Senior SRE & Diagnostic Specialist expert in fintech infrastructure and blockchain systems. "
                    "Your job is to analyze masked error logs alongside technical manual entries (RAG context). "
                    "You output ONLY a structured JSON object containing your analysis and action plan. "
                    "\n{format_instructions}"
                )),
                ("human", "Masked Log:\n{masked_log}\n\nTechnical Manual Context:\n{rag_context}")
            ])
            self._chain = prompt | self._llm | self.parser
        return self._chain

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def run_diagnosis(self, masked_log: str, rag_context: str) -> dict:
        """
        Executes the AI diagnosis process.
        """
        try:
            logger.info("Running AI diagnosis chain...")
            result = self.chain.invoke({
                "masked_log": masked_log,
                "rag_context": rag_context,
                "format_instructions": "The output MUST be a JSON object with: root_cause (str), action_plan (list of strings), risk_assessment (str), and advisor_notes (str)."
            })
            return result
        except Exception as e:
            logger.error(f"AI Diagnosis failed: {str(e)}")
            raise e
