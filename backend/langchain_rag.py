"""
LangChain-based RAG implementation for BudgetWise.
This provides a more structured, maintainable, and feature-rich implementation
compared to the custom FAISS implementation.
"""

import os
import json
from typing import List, Dict, Any, Optional, Union
import time
from datetime import datetime
import logging
from pathlib import Path

from langchain_google_genai import (
    ChatGoogleGenerativeAI
)
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

# Local imports
from database import get_db_connection
from config import get_api_key, validate_api_key, VECTOR_STORE_DIR, GEMINI_MODEL, EMBEDDING_MODEL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("langchain_rag")

# Get API key from config
GEMINI_API_KEY = get_api_key()

# Validate API key
if not validate_api_key():
    raise ValueError("Valid GEMINI_API_KEY is required for the LangChain RAG pipeline")

# Ensure the vector store directory exists
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
EMBEDDING_ID_FILE = os.path.join(VECTOR_STORE_DIR, "embedding_model.txt")

# Out-of-context guard message
OOC_MESSAGE = "I can only answer questions related to your expenses and financial insights."

# LangChain embeddings - switch to local HuggingFace to avoid API quotas
logger.info(f"Using embedding model={EMBEDDING_MODEL} (HuggingFace) gemini_model={GEMINI_MODEL} index_dir={VECTOR_STORE_DIR}")
_device = "mps"
try:
    import torch
    if not (hasattr(torch, "mps") and torch.backends.mps.is_available()):
        _device = "cpu"
        logger.warning("MPS not available; falling back to CPU for embeddings")
except Exception:
    _device = "mps"  # best-effort, SentenceTransformer will error if unsupported

embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": _device},
    encode_kwargs={"normalize_embeddings": True}
)
logger.info(f"HF embeddings device={_device}")

# Chunking configuration
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100,
    length_function=len,
)

class BudgetWiseRAG:
    """LangChain-based RAG for BudgetWise financial data."""
    
    def __init__(self):
        self.vector_store = None
        self._load_vector_store()

    # -------------------------------
    # Query relevance classification
    # -------------------------------
    def _is_query_relevant(self, query: str) -> bool:
        """Heuristic check to ensure the query is about personal finance in-app scope.
        Returns True if obviously finance/transactions related; False otherwise.
        """
        if not query:
            return False
        q = str(query).lower()

        # Core finance and app domain keywords/phrases
        keywords = {
            "expense", "expenses", "spend", "spent", "spending",
            "income", "earn", "earned", "salary", "wage", "paycheck",
            "budget", "savings", "save", "balance",
            "transaction", "transactions", "category", "categories",
            "rent", "food", "grocery", "groceries", "entertainment",
            "subscription", "subscriptions", "utilities", "electricity",
            "water", "gas", "fuel", "transport", "travel", "restaurant",
            "coffee", "bill", "bills", "due",
            "trend", "average", "total", "sum", "breakdown", "insight", "insights",
            "forecast", "recommendation", "recommendations",
            # time words and months to catch queries like "food in August"
            "daily", "weekly", "monthly", "yearly", "quarter",
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        }

        if any(k in q for k in keywords):
            return True

        # Money patterns
        money_markers = ["$", "usd", "dollar", "dollars"]
        if any(m in q for m in money_markers):
            return True

        # Common question forms tied to quantities/totals
        phrases = [
            "how much", "how many", "what is my", "show me", "compare",
            "list my", "sum of", "total of", "spending on", "income from",
        ]
        if any(p in q for p in phrases):
            return True

        return False
        
    @staticmethod
    def create_faiss_vectorstore(documents, index_name=VECTOR_STORE_DIR):
        """Create a FAISS vector store from documents."""
        if not documents:
            logger.warning("No documents provided to create vector store")
            return None
            
        vectorstore = FAISS.from_documents(documents, embeddings)
        vectorstore.save_local(index_name)
        # Persist embedding model fingerprint
        try:
            Path(index_name).mkdir(parents=True, exist_ok=True)
            with open(os.path.join(index_name, "embedding_model.txt"), "w") as f:
                f.write(EMBEDDING_MODEL)
        except Exception as e:
            logger.warning(f"Failed writing embedding fingerprint: {e}")
        return vectorstore
        
    def _load_vector_store(self):
        """Load the vector store if it exists."""
        try:
            if os.path.exists(os.path.join(VECTOR_STORE_DIR, "index.faiss")):
                # Check embedding model compatibility
                try:
                    with open(EMBEDDING_ID_FILE, "r") as f:
                        stored_model = f.read().strip()
                except Exception:
                    stored_model = None

                if (stored_model is None) or (stored_model != EMBEDDING_MODEL):
                    logger.warning(
                        f"Embedding model mismatch or missing: stored='{stored_model}' current='{EMBEDDING_MODEL}'. "
                        "Clearing old index to avoid incompatibility."
                    )
                    # Remove old index files
                    try:
                        for fname in ("index.faiss", "index.pkl"):
                            fpath = os.path.join(VECTOR_STORE_DIR, fname)
                            if os.path.exists(fpath):
                                os.remove(fpath)
                        if os.path.exists(EMBEDDING_ID_FILE):
                            os.remove(EMBEDDING_ID_FILE)
                    except Exception as e:
                        logger.warning(f"Failed to remove old index files: {e}")
                    self.vector_store = None
                    return
                logger.info("Loading existing FAISS index")
                self.vector_store = FAISS.load_local(
                    VECTOR_STORE_DIR,
                    embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"Loaded index with {len(self.vector_store.docstore._dict)} documents")
            else:
                logger.info("No existing FAISS index found")
                self.vector_store = None
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            self.vector_store = None

    def _format_transaction(self, transaction: Dict) -> str:
        """Format a transaction into a standardized string representation."""
        tx_date = transaction.get("date", "unknown_date")
        tx_type = transaction.get("type", "unknown_type") 
        tx_category = transaction.get("category", "uncategorized")
        tx_amount = transaction.get("amount", 0)
        tx_note = transaction.get("note", "")
        
        return (
            f"Transaction ID: {transaction.get('id')} | "
            f"User: {transaction.get('user_id')} | "
            f"Date: {tx_date} | "
            f"Type: {tx_type} | "
            f"Category: {tx_category} | "
            f"Amount: ${float(tx_amount):.2f} | "
            f"Note: {tx_note}"
        )

    def _create_metadata(self, transaction: Dict) -> Dict:
        """Create metadata for a transaction document."""
        return {
            "id": str(transaction.get("id")),
            "user_id": str(transaction.get("user_id")),
            "date": str(transaction.get("date")),
            "type": transaction.get("type", ""),
            "category": transaction.get("category", ""),
            "amount": str(float(transaction.get("amount", 0))),
            "note": transaction.get("note", ""),
        }
    
    def index_user_transactions(self, user_id: int, reindex: bool = False) -> int:
        """
        Index or reindex a user's transactions.
        
        Args:
            user_id: The user ID to index transactions for
            reindex: If True, recreate the user's portion of the index
            
        Returns:
            Number of transactions indexed
        """
        logger.info(f"Indexing transactions for user {user_id}, reindex={reindex}")
        
        # Connect to the database and get transactions
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, user_id, date, category, note, amount, type FROM expenses WHERE user_id=%s",
            (user_id,)
        )
        transactions = cursor.fetchall()
        conn.close()
        
        if not transactions:
            logger.info(f"No transactions found for user {user_id}")
            return 0
        
        # Process transactions into documents
        documents = []
        for tx in transactions:
            # Create the document text from the transaction
            content = self._format_transaction(tx)
            # Create metadata for filtering and reconstruction
            metadata = self._create_metadata(tx)
            # Create the document
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
            
        logger.info(f"Created {len(documents)} documents for indexing (user_id={user_id})")
        
        # Handle reindexing
        if reindex and self.vector_store is not None:
            # Since we can't easily delete by user_id, rebuild without those documents
            try:
                current_docs = getattr(self.vector_store.docstore, "_dict", {})
                filtered_docs = [
                    doc for _, doc in current_docs.items()
                    if doc.metadata.get("user_id") != str(user_id)
                ]
                if filtered_docs:
                    # Rebuild with only non-user documents
                    self.vector_store = FAISS.from_documents(filtered_docs, embeddings)
                else:
                    # No documents from other users, start fresh
                    self.vector_store = None
            except Exception as e:
                logger.error(f"Error during reindex filtering for user_id={user_id}: {e}")
                self.vector_store = None
        
        # Create or update the vector store with EFFICIENT BATCH embedding
        def _batch_create_or_update():
            # Prepare text and metadatas for batch embedding
            texts = []
            metadatas = []
            for doc in documents:
                texts.append(doc.page_content)
                metadatas.append(doc.metadata)
            
            logger.info(f"Preparing batch embedding for {len(texts)} documents")
            
            # Batch embed all documents in one API call
            try:
                logger.info("Calling embedding API in batch mode")
                vectors = embeddings.embed_documents(texts)
                logger.info(f"Successfully created {len(vectors)} embeddings")
                
                # If no existing store, create new one with all embeddings
                if self.vector_store is None:
                    logger.info("Creating new FAISS index from batch embeddings")
                    self.vector_store = FAISS.from_embeddings(
                        text_embeddings=list(zip(texts, vectors)),
                        embedding=embeddings,
                        metadatas=metadatas
                    )
                else:
                    # Add batch to existing store
                    logger.info(f"Adding {len(vectors)} embeddings to existing FAISS index")
                    self.vector_store.add_embeddings(
                        text_embeddings=list(zip(texts, vectors)),
                        metadatas=metadatas
                    )
                return True
            except Exception as e:
                logger.exception(f"Error in batch embedding: {e}")
                return False
        
        # First attempt
        success = _batch_create_or_update()
        
        # If failed and looks like rate limit, retry with more aggressive batching
        if not success:
            logger.warning("First batch attempt failed, will retry with smaller batches")
            try:
                # Split into smaller batches
                batch_size = 10  # reduced size for retry
                all_texts = []
                all_metadatas = []
                
                for doc in documents:
                    all_texts.append(doc.page_content)
                    all_metadatas.append(doc.metadata)
                
                # Process in smaller batches with delays
                for i in range(0, len(all_texts), batch_size):
                    batch_texts = all_texts[i:i+batch_size]
                    batch_metadatas = all_metadatas[i:i+batch_size]
                    
                    logger.info(f"Retry batch {i//batch_size + 1}: Processing {len(batch_texts)} documents")
                    vectors = embeddings.embed_documents(batch_texts)
                    
                    if self.vector_store is None:
                        self.vector_store = FAISS.from_embeddings(
                            text_embeddings=list(zip(batch_texts, vectors)),
                            embedding=embeddings,
                            metadatas=batch_metadatas
                        )
                    else:
                        self.vector_store.add_embeddings(
                            text_embeddings=list(zip(batch_texts, vectors)),
                            metadatas=batch_metadatas
                        )
                    
                    # Wait between batches
                    if i + batch_size < len(all_texts):
                        logger.info("Waiting between batches to avoid rate limits...")
                        time.sleep(0.5)
            except Exception as e:
                logger.exception(f"Batch retry failed: {e}")
                raise
            
        # Save the updated vector store
        self.vector_store.save_local(VECTOR_STORE_DIR)
        # Persist embedding model fingerprint
        try:
            with open(EMBEDDING_ID_FILE, "w") as f:
                f.write(EMBEDDING_MODEL)
        except Exception as e:
            logger.warning(f"Failed writing embedding fingerprint: {e}")
        logger.info(f"Saved index with {len(self.vector_store.docstore._dict)} total documents")
        return len(documents)
    
    def add_transaction_to_index(self, transaction: Dict) -> bool:
        """
        Add a single transaction to the index.
        
        Args:
            transaction: The transaction data to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Format the transaction text 
            text = f"Transaction ID: {transaction.get('id')} | User: {transaction.get('user_id')} | "
            text += f"Date: {transaction.get('date', 'unknown_date')} | Type: {transaction.get('type', 'unknown_type')} | "
            text += f"Category: {transaction.get('category', 'uncategorized')} | "
            text += f"Amount: ${float(transaction.get('amount', 0)):.2f} | Note: {transaction.get('note', '')}"
            
            # Create metadata
            metadata = self._create_metadata(transaction)
            
            # Get embedding in a single API call (even though it's just one doc)
            vector = embeddings.embed_documents([text])[0]
            
            # Add to the vector store
            if self.vector_store is None:
                logger.info("Creating new FAISS index for first transaction")
                self.vector_store = FAISS.from_embeddings(
                    text_embeddings=[(text, vector)],
                    embedding=embeddings,
                    metadatas=[metadata]
                )
            else:
                logger.info(f"Adding transaction {transaction.get('id')} to existing FAISS index")
                self.vector_store.add_embeddings(
                    text_embeddings=[(text, vector)],
                    metadatas=[metadata]
                )
                
            # Save the updated vector store
            self.vector_store.save_local(VECTOR_STORE_DIR)
            # Persist embedding model fingerprint
            try:
                with open(EMBEDDING_ID_FILE, "w") as f:
                    f.write(EMBEDDING_MODEL)
            except Exception as e:
                logger.warning(f"Failed writing embedding fingerprint: {e}")
            logger.info(f"Added transaction {transaction.get('id')} to index for user_id={transaction.get('user_id')}")
            return True
        except Exception as e:
            logger.exception(f"Error adding transaction to index: {e}")
            return False
            
    def get_relevant_transactions(self, user_id: int, query: str, top_k: int = 10) -> List[Dict]:
        """
        Retrieve relevant transactions for a user query.
        
        Args:
            user_id: The user ID to retrieve transactions for
            query: The natural language query
            top_k: Maximum number of results to return
            
        Returns:
            List of relevant transaction dictionaries with scores
        """
        if self.vector_store is None:
            logger.warning("No vector store available for retrieval")
            return []
            
        # Add user_id to query for better retrieval
        user_context_query = f"user:{user_id} {query}"
        
        # Search the vector store
        results = self.vector_store.similarity_search_with_score(
            user_context_query,
            k=top_k*2  # Get more results than needed to filter by user
        )
        
        # Filter to user_id and format results
        filtered_results = []
        seen_ids = set()  # Track seen transaction IDs to avoid duplicates
        
        for doc, score in results:
            doc_user_id = doc.metadata.get("user_id")
            if doc_user_id != str(user_id):
                continue
                
            tx_id = doc.metadata.get("id")
            if tx_id in seen_ids:
                continue
                
            seen_ids.add(tx_id)
            
            # Convert score to similarity (FAISS returns distance, smaller is more similar)
            similarity = float(score)
            
            # Create a transaction dictionary from metadata
            transaction = {
                "id": int(doc.metadata.get("id")),
                "user_id": int(doc.metadata.get("user_id")),
                "date": doc.metadata.get("date"),
                "type": doc.metadata.get("type"),
                "category": doc.metadata.get("category"),
                "amount": float(doc.metadata.get("amount")),
                "note": doc.metadata.get("note"),
                "score": similarity
            }
            
            filtered_results.append(transaction)
            
            # Stop when we have enough results
            if len(filtered_results) >= top_k:
                break
                
        logger.info(f"Retrieved {len(filtered_results)} matches for user_id={user_id} query='{query[:60]}'")
        return filtered_results
    
    def _setup_rag_pipeline(self):
        """
        Set up the RAG pipeline using RetrievalQA chain.
        Similar to the reference rag_pipeline.py.
        """
        if not self.vector_store:
            logger.warning("Cannot set up RAG pipeline without vector store")
            return None

        prompt_template = """
                You are a friendly and helpful personal finance assistant for BudgetWise.
                Answer questions naturally using ONLY the provided transaction data. Be conversational and direct.

                IMPORTANT SCOPE RULE:
                - If the question is outside personal finance, transactions, budgets, or spending/income insights,
                    respond EXACTLY with: """ + OOC_MESSAGE + """
                - Do not answer general knowledge or unrelated questions.
            
                Response guidelines:
                - Start with a direct answer to their question
                - Be conversational and natural - write like you're talking to a friend
                - Use specific numbers and dates from the transactions
                - Highlight important amounts in bold (e.g., **$123.45**)
                - Group information logically but don't force strict sections
                - Add helpful insights or patterns you notice
                - Keep currency values to 2 decimals
                - If data is limited, say so naturally and suggest what might help
                - Do not invent or assume data not in the context
            
                Analysis approach:
                - For spending questions: Sum amounts and highlight categories
                - For trends: Note patterns over time naturally
                - For comparisons: Show the differences clearly
                - For category questions: Group and provide totals
            
                Context:
                {context}
            
                Question: {question}
                Answer:
                """

        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )

        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY,
            temperature=0.4,  # Increased for more natural, conversational responses
            convert_system_message_to_human=True,
            safety_settings=[
                {
                    "category": "harassment",
                    "threshold": "block_none"
                },
                {
                    "category": "hate_speech",
                    "threshold": "block_none" 
                },
                {
                    "category": "sexually_explicit",
                    "threshold": "block_none"
                },
                {
                    "category": "dangerous_content",
                    "threshold": "block_none"
                }
            ]
        )

        return RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=self.vector_store.as_retriever(search_kwargs={"k": 8}),  # Increased to 8 for better context
            return_source_documents=True,
            chain_type_kwargs={"prompt": prompt}
        )
        
    def generate_answer(self, user_id: int, query: str, matches: List[Dict]) -> str:
        """
        Generate an answer using retrieved matches and the Gemini model.
        
        Args:
            user_id: User ID for context
            query: The original user query
            matches: List of retrieved transaction dictionaries
            
        Returns:
            Generated answer text
        """
        # Guard: out-of-scope queries return a fixed message
        if not self._is_query_relevant(query):
            return OOC_MESSAGE

        if not matches:
            return "I couldn't find any relevant transactions to answer your question. Try rephrasing or ask about different transactions."
        
        # Format the transactions for the context
        formatted_transactions = []
        for tx in matches:
            tx_str = (
                f"Transaction ID: {tx.get('id')} | "
                f"User: {tx.get('user_id')} | "
                f"Date: {tx.get('date')} | "
                f"Type: {tx.get('type')} | "
                f"Category: {tx.get('category')} | "
                f"Amount: ${float(tx.get('amount')):.2f} | "
                f"Note: {tx.get('note')}"
            )
            formatted_transactions.append(tx_str)
            
        context = "\n".join(formatted_transactions)
        
        # Use RetrievalQA chain if vector store is available, otherwise use direct generation
        try:
            if self.vector_store is not None:
                # Using metadata filter for user-specific context
                filtered_retriever = self.vector_store.as_retriever(
                    search_kwargs={"k": 12, "filter": {"user_id": str(user_id)}}  # Increased for richer context
                )
                
                # Create an LLM for direct query
                llm = ChatGoogleGenerativeAI(
                    model=GEMINI_MODEL,
                    google_api_key=GEMINI_API_KEY,
                    temperature=0.4  # Increased for more natural responses
                )
                
                # User-specific prompt
                prompt_template = """
                                You are a friendly personal finance assistant for BudgetWise.
                                Answer naturally using ONLY the provided transaction data. Be conversational and helpful.

                                IMPORTANT SCOPE RULE:
                                - If the question is outside personal finance, transactions, budgets, or spending/income insights,
                                    respond EXACTLY with: """ + OOC_MESSAGE + """
                                - Do not answer unrelated topics.
                
                                Response guidelines:
                                - Start with a direct, natural answer
                                - Be conversational - like talking to a friend
                                - Use specific numbers from the transactions
                                - Bold important amounts like **$X.XX**
                                - Share useful insights you notice
                                - Keep it concise but informative (around 150-200 words)
                                - If data is limited, say so naturally
                
                                Transactions:
                                {context}
                
                                Question: {question}
                                Answer:
                                """
                
                prompt = PromptTemplate(
                    template=prompt_template,
                    input_variables=["context", "question"]
                )
                
                # Create chain
                qa_chain = RetrievalQA.from_chain_type(
                    llm=llm,
                    chain_type="stuff",
                    retriever=filtered_retriever,
                    return_source_documents=False,
                    chain_type_kwargs={"prompt": prompt}
                )
                
                # Run the chain
                result = qa_chain.invoke({"query": query})
                return result.get("result", "I couldn't generate a proper answer. Please try again.")
            else:
                # Fallback to direct LLM if no vector store
                llm = ChatGoogleGenerativeAI(
                    model=GEMINI_MODEL,
                    google_api_key=GEMINI_API_KEY,
                    temperature=0.4  # Increased for more natural responses
                )
                
                messages = [
                    SystemMessage(content=(
                        "You are a friendly personal finance assistant. Answer naturally based only on the provided transactions. "
                        "Be conversational and helpful. Use specific numbers and dates. Bold important amounts. "
                        "If the question is outside personal finance/transactions/budgets, respond EXACTLY with: " + OOC_MESSAGE
                    )),
                    HumanMessage(content=f"My question is: {query}\n\nHere are my relevant transactions:\n{context}")
                ]
                
                response = llm.invoke(messages)
                return response.content
                
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"I had trouble analyzing your transactions. Please try again. Technical details: {str(e)[:100]}"
            
    def query_with_rag(self, user_id: int, query: str, top_k: int = 10) -> Dict:
        """
        Complete RAG pipeline: retrieve relevant transactions and generate an answer.
        Uses LangChain's RetrievalQA for more structured retrieval and generation.
        
        Args:
            user_id: User ID for context
            query: The user's question about their finances
            top_k: Number of relevant transactions to retrieve
            
        Returns:
            Dictionary with answer and matches
        """
        try:
            # Out-of-scope guard before hitting retrieval/LLM
            if not self._is_query_relevant(query):
                return {"answer": OOC_MESSAGE, "matches": []}

            # Check if index exists for this user
            if self.vector_store is None:
                return {
                    "answer": "Your financial data hasn't been indexed yet. Please build the index first.",
                    "matches": []
                }
                
            # Retrieve relevant transactions
            matches = self.get_relevant_transactions(user_id, query, top_k)
            
            # Generate an answer
            answer = self.generate_answer(user_id, query, matches)
            
            # Return both the answer and the matches for transparency
            return {
                "answer": answer,
                "matches": matches
            }
        except Exception as e:
            logger.error(f"Error in RAG pipeline: {e}")
            return {
                "answer": f"An error occurred while processing your question. Please try again later. Error: {str(e)[:100]}",
                "matches": []
            }
        
    def get_index_stats(self) -> Dict:
        """Get statistics about the current index."""
        stats = {
            "total_documents": 0,
            "users": {},
            "document_types": {},
            "categories": {},
            "index_size_kb": 0,
            "last_modified": None
        }
        
        if self.vector_store is None:
            return stats
            
        # Count documents and categorize
        user_counts = {}
        doc_types = {}
        categories = {}
        
        for doc_id, doc in self.vector_store.docstore._dict.items():
            stats["total_documents"] += 1
            
            user_id = doc.metadata.get("user_id")
            if user_id:
                user_counts[user_id] = user_counts.get(user_id, 0) + 1
                
            doc_type = doc.metadata.get("type")
            if doc_type:
                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                
            category = doc.metadata.get("category")
            if category:
                categories[category] = categories.get(category, 0) + 1
                
        stats["users"] = user_counts
        stats["document_types"] = doc_types
        stats["categories"] = categories
        
        # Get index file size if available
        index_path = os.path.join(VECTOR_STORE_DIR, "index.faiss")
        if os.path.exists(index_path):
            stats["index_size_kb"] = os.path.getsize(index_path) / 1024
            stats["last_modified"] = datetime.fromtimestamp(
                os.path.getmtime(index_path)
            ).isoformat()
            
        return stats


# Initialize the global RAG instance
rag_service = BudgetWiseRAG()