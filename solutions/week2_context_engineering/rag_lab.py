import requests
import json
import chromadb
import argparse
from difflib import Differ
from pprint import pprint

# --- 1. Configuration ---
OLLAMA_ENDPOINT = "http://localhost:11434/api"
OLLAMA_CONFIG = {
    "model": "llama3",
    "stream": False,
}
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "faq_collection"

# --- 2. Knowledge Base ---
# In a real-world scenario, this would come from a file, database, or API.
FAQ_DATA = []
AUG_CONTEXT_SEPARATOR = "---CONTEXT BLOCK {i}---"

# --- 3. ChromaDB Setup ---
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection(name=COLLECTION_NAME)

# --- 4. Helper Functions ---


def get_embedding(text):
    """
    Generates an embedding for the given text using the Ollama API.
    """
    try:
        response = requests.post(
            f"{OLLAMA_ENDPOINT}/embeddings",
            json={"model": OLLAMA_CONFIG["model"], "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except requests.exceptions.RequestException as e:
        print(f"Error getting embedding: {e}")
        return None


def index_knowledge_base():
    """
    Indexes the knowledge base into ChromaDB.
    """
    print("Indexing knowledge base...")
    for item in FAQ_DATA:
        # We are embedding the questions to find similar user queries.
        embedding = get_embedding(item["question"])
        if embedding:
            collection.add(
                ids=[item["id"]],
                embeddings=[embedding],
                documents=[item["answer"]],  # Store the answer as the document
                metadatas=[{"question": item["question"]}],
            )
    print("Indexing complete.")


def query_rag_agent(
    user_query="Do not answer anything", use_aug_context=False, aug_context_results=2
):
    """
    Queries the RAG agent with a user's question.
    """
    # print(f"\n--- Querying for: '{user_query}' ---")

    # 1. Get embedding for the user query
    retrieved_context = ""
    if use_aug_context:
        query_embedding = get_embedding(user_query)
        if not query_embedding:
            return "Sorry, I couldn't process your query."

        # 2. Query ChromaDB for relevant context
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=aug_context_results,  # Retrieve the top 2 most relevant documents
        )

        for counter, context in enumerate(results["documents"][0]):
            retrieved_context = (
                retrieved_context
                + "\n"
                + AUG_CONTEXT_SEPARATOR.format(i=counter)
                + context
                if results["documents"]
                else "No relevant information found."
            )

        print(f"Retrieved context: {retrieved_context}")

    # 3. Construct the prompt for the LLM
    prompt = f"""
    You are a helpful FAQ assistant. A user has asked the following question:
    '{user_query}'
    If there is not enough information to answer the question just say so.
    """

    if use_aug_context:
        prompt = (
            prompt
            + f"""
    Here is some context that might be relevant:
    '{retrieved_context}'

    Based on this context, please provide a clear and concise answer. If the context is not relevant, say so.

    Finally, include which context blocks were used to resolve the question. Use output format "FAQs used:  [CONTEXT BLOCK 0, CONTEXT BLOCK 1]" style list.
        """
        )
    # print(f"--- Used prompt: {prompt}")

    # 4. Send the prompt to the LLM
    try:
        response = requests.post(
            f"{OLLAMA_ENDPOINT}/generate", json={"prompt": prompt, **OLLAMA_CONFIG}
        )
        response.raise_for_status()
        return json.loads(response.text)["response"]
    except requests.exceptions.RequestException as e:
        return f"Error communicating with the model: {e}"


# --- 5. Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CLI tool that handles LLM queries. Parameters --k, --no-context, and --query."
    )

    # Add arguments
    parser.add_argument(
        "--k",
        type=int,
        default=2,
        help="Number of results or items to process (default: 2).",
    )

    parser.add_argument(
        "--no-context",
        action="store_true",
        help="If set, disables augmented context usage.",
    )

    parser.add_argument(
        "--query", type=str, required=True, help="The query string to process."
    )

    # Parse the arguments from the command line
    args = parser.parse_args()

    # Example usage of parsed arguments
    print(f"Query: {args.query}")
    print(f"k: {args.k}")
    print(f"No context: {args.no_context}")

    with open("resources/faq_data.json", "r") as file:
        FAQ_DATA = json.load(file)

    # Check if the collection is empty before indexing
    if collection.count() == 0:
        index_knowledge_base()
    else:
        print("Knowledge base is already indexed.")

    # --- Test Queries ---
    if args.no_context:
        print("Querying without added context")
        answer1 = query_rag_agent(args.query, not args.no_context, args.k).splitlines(
            keepends=True
        )
        print("Querying with added context")
        answer2 = query_rag_agent(args.query, args.no_context, args.k).splitlines(
            keepends=True
        )
        d = Differ()
        output_list = list(d.compare(answer1, answer2))
        print("Differences: ")
        pprint(output_list)
    else:
        answer = query_rag_agent(args.query, args.no_context, args.k)
        print(f"Answer: {answer}")
