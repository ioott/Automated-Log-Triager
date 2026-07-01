import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a Senior SRE & Diagnostic Specialist expert in fintech "
            "infrastructure and blockchain ledger systems. Analyze masked "
            "error logs alongside technical manual entries. Output ONLY a "
            "valid JSON object with no markdown fences."
        ),
    ),
    (
        "human",
        (
            "Analyze the following masked log:\n{masked_log}\n\n"
            "Using the context from the technical manual:\n{rag_context}\n\n"
            "Return a JSON object with exactly these keys:\n"
            "- root_cause: string describing the likely root cause\n"
            "- action_plan: list of strings with step-by-step actions "
            "for the SRE team\n"
            "- risk_assessment: one of CRITICAL, HIGH, MEDIUM, or LOW. "
            "If the technical manual context states a Known Risk Level, "
            "use that value exactly unless the log strongly contradicts it\n"
            "- advisor_notes: string with additional observations or caveats"
        ),
    ),
])


class DiagnosticAgent:
    """
    AI Diagnostic Agent for triaging transaction logs using RAG context.
    Uses a LangChain prompt→LLM→JSON chain backed by Google Gemini.
    """

    def __init__(self):
        if (
            not settings.GOOGLE_API_KEY
            or settings.GOOGLE_API_KEY == "placeholder-key"
        ):
            raise ValueError("GOOGLE_API_KEY is not configured.")

        model_name = settings.GEMINI_MODEL_NAME
        if model_name.startswith("models/"):
            model_name = model_name[len("models/"):]

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0,
        )

        self._chain = _PROMPT | llm | JsonOutputParser()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def run_diagnosis(
        self, masked_log: str, rag_context: str
    ) -> dict:
        """Executes AI diagnosis via a LangChain prompt→LLM→JSON chain."""
        logger.info("Running LangChain diagnosis chain...")
        try:
            return await self._chain.ainvoke(
                {"masked_log": masked_log, "rag_context": rag_context}
            )
        except Exception as e:
            logger.error(f"Diagnosis chain failed: {e}")
            raise
