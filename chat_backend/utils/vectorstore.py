import PyPDF2
import faiss
import numpy as np
import tiktoken
import os
import pickle
import streamlit as st
import uuid
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from django.conf import settings

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return None

def chunk_text(text, chunk_size=500, overlap=50):
    """Split text into overlapping chunks for better context retention"""
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    
    chunks = []
    for i in range(0, len(tokens), chunk_size - overlap):
        chunk_tokens = tokens[i:i + chunk_size]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
    
    return chunks

class VectorStore:
    """Lightweight vector store using FAISS with unique PDF IDs"""
    
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model
        self.index = None
        self.documents = []
        self.embeddings = []
        self.pdf_registry = {}  # Maps PDF ID to metadata
        
    def add_documents(self, texts, filename, pdf_id=None):
        """Add documents to the vector store with unique PDF ID"""
        # Generate unique PDF ID if not provided
        if pdf_id is None:
            pdf_id = str(uuid.uuid4())
        
        # Register PDF in registry
        self.pdf_registry[pdf_id] = {
            'filename': filename,
            'chunk_count': len(texts),
            'created_at': str(uuid.uuid1().time)
        }
        
        # Generate embeddings using Google Generative AI
        embeddings = self.embedding_model.embed_documents(texts)
        embeddings = np.array(embeddings)
        
        # Initialize or update FAISS index
        if self.index is None:
            self.index = faiss.IndexFlatIP(embeddings.shape[1])  # Inner product for cosine similarity
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to index
        self.index.add(embeddings.astype('float32'))
        
        # Store documents with metadata including PDF ID
        for i, text in enumerate(texts):
            self.documents.append({
                'text': text,
                'filename': filename,
                'pdf_id': pdf_id,
                'chunk_id': len(self.documents),
                'chunk_index': i  # Index within the PDF
            })
        
        self.embeddings.extend(embeddings)
        return pdf_id
    
    def search(self, query, k=3, pdf_id=None):
        """Search for similar documents, optionally filtered by PDF ID"""
        if self.index is None or len(self.documents) == 0:
            return []
        
        # Generate query embedding using Google Generative AI
        query_embedding = self.embedding_model.embed_query(query)
        query_embedding = np.array([query_embedding])
        faiss.normalize_L2(query_embedding)
        
        # Search with larger k if filtering by PDF ID
        search_k = k * 10 if pdf_id else k
        scores, indices = self.index.search(query_embedding.astype('float32'), min(search_k, len(self.documents)))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            # Convert numpy types to Python int for comparison
            idx = int(idx)
            if idx >= 0 and idx < len(self.documents):
                document = self.documents[idx]
                
                # Filter by PDF ID if specified
                if pdf_id and document['pdf_id'] != pdf_id:
                    continue
                
                results.append({
                    'text': document['text'],
                    'filename': document['filename'],
                    'pdf_id': document['pdf_id'],
                    'chunk_id': document['chunk_id'],
                    'chunk_index': document['chunk_index'],
                    'score': float(score)
                })
                
                # Stop if we have enough results
                if len(results) >= k:
                    break
        
        return results
    
    def get_pdf_info(self, pdf_id):
        """Get information about a specific PDF"""
        return self.pdf_registry.get(pdf_id)
    
    def list_pdfs(self):
        """List all PDFs in the vector store"""
        return self.pdf_registry
    
    def remove_pdf(self, pdf_id):
        """Remove a PDF and all its chunks from the vector store"""
        if pdf_id not in self.pdf_registry:
            return False
        
        # Find indices of documents to remove
        indices_to_remove = []
        for i, doc in enumerate(self.documents):
            if doc['pdf_id'] == pdf_id:
                indices_to_remove.append(i)
        
        if not indices_to_remove:
            return False
        
        # Remove documents and embeddings (in reverse order to maintain indices)
        for idx in reversed(indices_to_remove):
            self.documents.pop(idx)
            self.embeddings.pop(idx)
        
        # Remove from registry
        del self.pdf_registry[pdf_id]
        
        # Rebuild FAISS index
        if self.embeddings:
            embeddings_array = np.array(self.embeddings)
            self.index = faiss.IndexFlatIP(embeddings_array.shape[1])
            faiss.normalize_L2(embeddings_array)
            self.index.add(embeddings_array.astype('float32'))
        else:
            self.index = None
        
        return True
    
    def save(self, filepath):
        """Save vector store to file"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {
            'documents': self.documents,
            'embeddings': self.embeddings,
            'pdf_registry': self.pdf_registry,
            'index': faiss.serialize_index(self.index) if self.index else None
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
    
    def load(self, filepath):
        """Load vector store from file"""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    data = pickle.load(f)
                self.documents = data.get('documents', [])
                self.embeddings = data.get('embeddings', [])
                self.pdf_registry = data.get('pdf_registry', {})
                if data.get('index'):
                    self.index = faiss.deserialize_index(data['index'])
                else:
                    self.index = None
                return True
            except Exception as e:
                st.error(f"Error loading vector store: {str(e)}")
                # Reset to empty state on error
                self.documents = []
                self.embeddings = []
                self.pdf_registry = {}
                self.index = None
        return False


def load_embedding_model():
    """Load the Google Generative AI embedding model"""
    return GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL)


def get_vector_store():
    """Get or create vector store"""
    embedding_model = load_embedding_model()
    vector_store = VectorStore(embedding_model)
    vector_store.load(settings.VECTOR_STORE_FILE)
    return vector_store


def process_pdf_upload(uploaded_file, pdf_id=None):
    """Process uploaded PDF and add to vector store with unique ID"""
    if uploaded_file is not None:
        # Extract text
        text = extract_text_from_pdf(uploaded_file)
        if text:
            # Chunk text
            chunks = chunk_text(text)

            # Add to vector store
            vector_store = get_vector_store()
            pdf_id = vector_store.add_documents(chunks, uploaded_file.name, pdf_id)
            vector_store.save(settings.VECTOR_STORE_FILE)

            return pdf_id, len(chunks)
    return None, 0


def get_rag_context(query, vector_store, max_chunks=3, pdf_id=None):
    """Get relevant context from vector store for RAG, optionally filtered by PDF ID"""
    results = vector_store.search(query, k=max_chunks, pdf_id=pdf_id)

    if not results:
        return ""

    context_parts = []
    for result in results:
        context_parts.append(f"[From {result['filename']} (PDF ID: {result['pdf_id'][:8]}...)]: {result['text']}")

    return "\n\n".join(context_parts)
