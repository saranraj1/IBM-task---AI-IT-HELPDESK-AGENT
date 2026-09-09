import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

try:
    import torch
except Exception:
    pass

from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import (
    EMBEDDING_MODEL_NAME,
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIRECTORY,
    KNOWLEDGE_BASE_DIR,
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
    RAG_TOP_K
)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
KB_DIR = BASE_DIR / KNOWLEDGE_BASE_DIR
CHROMA_DIR = BASE_DIR / CHROMA_PERSIST_DIRECTORY

_vectorstore = None
_embeddings = None

class SimpleFallbackVectorStore:
    """Fast, zero-dependency in-memory vector store fallback if ChromaDB is not installed or unavailable."""
    def __init__(self, docs: list, embeddings):
        import numpy as np
        self.docs = docs
        self.embeddings = embeddings
        texts = [d.page_content for d in docs]
        if texts:
            self.doc_vectors = np.array(embeddings.embed_documents(texts))
        else:
            self.doc_vectors = np.empty((0, 384))

    def similarity_search(self, query: str, k: int = 3) -> list:
        import numpy as np
        if not self.docs or len(self.doc_vectors) == 0:
            return []
        q_vec = np.array(self.embeddings.embed_query(query))
        norms = np.linalg.norm(self.doc_vectors, axis=1) * np.linalg.norm(q_vec)
        norms[norms == 0] = 1e-10
        scores = np.dot(self.doc_vectors, q_vec) / norms
        top_indices = np.argsort(scores)[::-1][:k]
        return [self.docs[i] for i in top_indices]

    @property
    def _collection(self):
        class DummyCollection:
            def count(s):
                return len(self.docs)
        return DummyCollection()

    def delete_collection(self):
        self.docs = []
        self.doc_vectors = None

def get_embeddings():
    """Lazy load HuggingFace Embeddings model."""
    global _embeddings
    if _embeddings is None:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    return _embeddings

def _load_all_kb_documents() -> list:
    """Loads all knowledge base documents (.txt and .md) from KB_DIR."""
    if not KB_DIR.exists():
        KB_DIR.mkdir(parents=True, exist_ok=True)

    docs = []
    # Load .txt documents
    txt_loader = DirectoryLoader(
        str(KB_DIR),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}
    )
    docs.extend(txt_loader.load())

    # Load .md documents
    md_loader = DirectoryLoader(
        str(KB_DIR),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}
    )
    docs.extend(md_loader.load())

    return docs

def reindex_knowledge_base(force: bool = True) -> int:
    """
    Forces a complete rebuild of the vector collection from KB documents.
    Attempts ChromaDB first, with automatic fallback to in-memory embedding search.
    """
    global _vectorstore
    embeddings = get_embeddings()
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    if force and _vectorstore is not None:
        try:
            _vectorstore.delete_collection()
        except Exception:
            pass
        _vectorstore = None

    docs = _load_all_kb_documents()
    if not docs:
        print("[RAG Warning] No documents found to index in knowledge_base/")
        _vectorstore = SimpleFallbackVectorStore([], embeddings)
        return 0

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=RAG_CHUNK_SIZE,
        chunk_overlap=RAG_CHUNK_OVERLAP
    )
    splits = text_splitter.split_documents(docs)

    # 1. Try ChromaDB
    try:
        from langchain_community.vectorstores import Chroma
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            collection_name=CHROMA_COLLECTION_NAME,
            persist_directory=str(CHROMA_DIR)
        )
        _vectorstore = vectorstore
        return vectorstore._collection.count()
    except Exception as e:
        print(f"[RAG Info] ChromaDB unavailable ({e}). Activated In-Memory Embedding Index.")
        _vectorstore = SimpleFallbackVectorStore(splits, embeddings)
        return len(splits)

def get_or_create_vectorstore():
    """Initializes or loads the vector database from knowledge_base/ documents."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    embeddings = get_embeddings()
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from langchain_community.vectorstores import Chroma
        vectorstore = Chroma(
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(CHROMA_DIR)
        )
        if vectorstore._collection.count() > 0:
            _vectorstore = vectorstore
            return _vectorstore
    except Exception:
        pass

    reindex_knowledge_base(force=False)
    return _vectorstore

def query_rag(query: str, top_k: int = RAG_TOP_K) -> dict:
    """
    Queries vectorstore and retrieves top_k relevant doc chunks.
    Returns dict: {'chunks': list, 'sources': list, 'context': str}
    """
    try:
        vs = get_or_create_vectorstore()
        results = vs.similarity_search(query, k=top_k)
        chunks = [doc.page_content for doc in results]
        sources = list({Path(doc.metadata.get("source", "knowledge_base")).name for doc in results if doc.metadata})
        context = "\n---\n".join(chunks)
        return {"chunks": chunks, "sources": sources, "context": context}
    except Exception as e:
        print(f"[RAG Error] Query failed: {e}")
        return {"chunks": [], "sources": [], "context": f"Failed to retrieve context from knowledge base: {e}"}

def get_indexed_chunk_count() -> int:
    """Returns the total number of chunks currently indexed."""
    try:
        vs = get_or_create_vectorstore()
        return vs._collection.count()
    except Exception:
        return 0
