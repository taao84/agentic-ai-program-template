import asyncio

from agno.agent import Agent
from agno.knowledge.knowledge import Knowledge
from agno.models.ollama import Ollama
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.vectordb.chroma import ChromaDb
from agno.os import AgentOS
from agno.db.sqlite import SqliteDb

contents_db = SqliteDb(db_file="db/my_knowledge.db")

# Create Knowledge Instance with ChromaDB
knowledge = Knowledge(
    name="Basic SDK Knowledge Base",
    description="Agno 2.0 Knowledge Implementation with ChromaDB",
    vector_db=ChromaDb(
        collection="vectors",
        path="tmp/chromadb",
        persistent_client=True,
        embedder=OllamaEmbedder(id="llama3.1", dimensions=4096),
    ),
    contents_db=contents_db,
)

asyncio.run(
    knowledge.add_content_async(
        name="Recipes",
        url="https://agno-public.s3.amazonaws.com/recipes/ThaiRecipes.pdf",
        metadata={"doc_type": "recipe_book"},
    )
)

# Create and use the agent
rag_assistant_agent = Agent(
    name="RAG Assistant",
    model=Ollama(id="mistral:7b"),
    markdown=True,
    knowledge=knowledge,
)

print(rag_assistant_agent.run("Give me the best breakfast Thai recipe"))

# Create the AgentOS
agent_os = AgentOS(agents=[rag_assistant_agent])
# Get the FastAPI app for the AgentOS
app = agent_os.get_app()
