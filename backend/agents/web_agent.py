from livekit.agents import (Agent, 
                            function_tool,
                            RunContext)
import chromadb
import logging
from openai import OpenAI
from agents.agent_prompts import WEB_AGENT_PROMPT

logger = logging.getLogger("agent")

class Webagent(Agent):
    def __init__(self) -> None:
        super().__init__(
            # Instructions for the agent
            instructions=WEB_AGENT_PROMPT,
        )
        self.chroma_client = chromadb.PersistentClient(path="./vector_db")
        self.collection = self.chroma_client.get_or_create_collection(name="indusnet_website")
        self.db_fetch_size = 5
    
    @function_tool
    async def lookup_website_information(self, context: RunContext, question: str):
        """Use this tool to answer any questions about Indus net Technologies."""
        logger.info(f"looking for {question}")
        results = self.collection.query(
                query_texts=[question],
                n_results=self.db_fetch_size
            )
        documents = results.get("documents", [])
        
        # Flatten and join all text into a single clean markdown string
        flat_documents = [item for sublist in documents for item in sublist]
        joined = "\n\n---\n\n".join(doc.strip() for doc in flat_documents if doc.strip())

        # Optionally strip excessive whitespace, remove duplicate consecutive lines
        cleaned = "\n".join(line for i, line in enumerate(joined.splitlines()) 
                            if line.strip() and (i == 0 or line.strip() != joined.splitlines()[i-1].strip()))

        return cleaned
