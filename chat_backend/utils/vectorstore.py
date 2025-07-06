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
    """Lightweight vector store using FAISS with unique PDF IDs and separate file storage"""
    
    def __init__(self, embedding_model, storage_dir=None):
        self.embedding_model = embedding_model
        self.storage_dir = storage_dir or os.path.join(os.path.dirname(settings.VECTOR_STORE_FILE), 'pdf_vectorstores')
        self.index = None
        self.documents = []
        self.embeddings = []
        self.pdf_registry = {}  # Maps PDF ID to metadata
        
        # Ensure storage directory exists
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _get_pdf_file_path(self, pdf_id):
        """Get file path for a specific PDF's vector store data"""
        return os.path.join(self.storage_dir, f"{pdf_id}.pkl")
    
    def _get_registry_file_path(self):
        """Get file path for the PDF registry"""
        return os.path.join(self.storage_dir, "pdf_registry.pkl")
        
    def add_documents(self, texts, filename, pdf_id=None):
        """Add documents to the vector store with unique PDF ID and save separately"""
        # Generate unique PDF ID if not provided
        if pdf_id is None:
            pdf_id = str(uuid.uuid4())
        
        # Generate embeddings using Google Generative AI
        embeddings = self.embedding_model.embed_documents(texts)
        embeddings = np.array(embeddings, dtype=np.float32)
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Create FAISS index for this PDF
        pdf_index = faiss.IndexFlatIP(embeddings.shape[1])
        pdf_index.add(embeddings.astype('float32'))
        
        # Store documents with metadata
        pdf_documents = []
        for i, text in enumerate(texts):
            pdf_documents.append({
                'text': text,
                'filename': filename,
                'pdf_id': pdf_id,
                'chunk_id': i,
                'chunk_index': i
            })
        
        # Save PDF data to separate file
        pdf_data = {
            'pdf_id': pdf_id,
            'filename': filename,
            'documents': pdf_documents,
            'embeddings': embeddings.tolist(),
            'index': faiss.serialize_index(pdf_index),
            'created_at': str(uuid.uuid1().time)
        }
        
        pdf_file_path = self._get_pdf_file_path(pdf_id)
        with open(pdf_file_path, 'wb') as f:
            pickle.dump(pdf_data, f)
        
        # Register PDF in registry
        self.pdf_registry[pdf_id] = {
            'filename': filename,
            'chunk_count': len(texts),
            'created_at': pdf_data['created_at'],
            'file_path': pdf_file_path
        }
        
        # Save updated registry
        self._save_registry()
        
        # Reload the combined index
        self._rebuild_combined_index()
        
        return pdf_id
    
    def _rebuild_combined_index(self):
        """Rebuild the combined index from all PDF files"""
        self.documents = []
        self.embeddings = []
        all_embeddings = []
        
        for pdf_id in self.pdf_registry:
            pdf_data = self._load_pdf_data(pdf_id)
            if pdf_data:
                self.documents.extend(pdf_data['documents'])
                pdf_embeddings = np.array(pdf_data['embeddings'], dtype=np.float32)
                self.embeddings.extend(pdf_embeddings)
                all_embeddings.append(pdf_embeddings)
        
        if all_embeddings:
            combined_embeddings = np.vstack(all_embeddings)
            self.index = faiss.IndexFlatIP(combined_embeddings.shape[1])
            faiss.normalize_L2(combined_embeddings)
            self.index.add(combined_embeddings.astype('float32'))
        else:
            self.index = None
    
    def _load_pdf_data(self, pdf_id):
        """Load data for a specific PDF"""
        pdf_file_path = self._get_pdf_file_path(pdf_id)
        if os.path.exists(pdf_file_path):
            try:
                with open(pdf_file_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                st.error(f"Error loading PDF data for {pdf_id}: {str(e)}")
        return None
    
    def _save_registry(self):
        """Save the PDF registry"""
        registry_path = self._get_registry_file_path()
        with open(registry_path, 'wb') as f:
            pickle.dump(self.pdf_registry, f)
    
    def _load_registry(self):
        """Load the PDF registry"""
        registry_path = self._get_registry_file_path()
        if os.path.exists(registry_path):
            try:
                with open(registry_path, 'rb') as f:
                    self.pdf_registry = pickle.load(f)
                return True
            except Exception as e:
                st.error(f"Error loading PDF registry: {str(e)}")
                self.pdf_registry = {}
        return False
    
    def search(self, query, k=3, pdf_id=None):
        """Search for similar documents, optionally filtered by PDF ID"""
        if pdf_id:
            # Search within specific PDF
            pdf_data = self._load_pdf_data(pdf_id)
            if not pdf_data:
                return []
            
            # Create temporary index for this PDF
            embeddings = np.array(pdf_data['embeddings'], dtype=np.float32)
            if len(embeddings) == 0:
                return []
            
            temp_index = faiss.IndexFlatIP(embeddings.shape[1])
            faiss.normalize_L2(embeddings)
            temp_index.add(embeddings)
            
            # Generate query embedding
            query_embedding = self.embedding_model.embed_query(query)
            query_embedding = np.array([query_embedding], dtype=np.float32)
            faiss.normalize_L2(query_embedding)
            
            # Search
            scores, indices = temp_index.search(query_embedding, min(k, len(pdf_data['documents'])))
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                idx = int(idx)
                if idx >= 0 and idx < len(pdf_data['documents']):
                    document = pdf_data['documents'][idx]
                    results.append({
                        'text': document['text'],
                        'filename': document['filename'],
                        'pdf_id': document['pdf_id'],
                        'chunk_id': document['chunk_id'],
                        'chunk_index': document['chunk_index'],
                        'score': float(score)
                    })
            
            return results
        else:
            # Search across all PDFs using combined index
            if self.index is None or len(self.documents) == 0:
                return []
            
            # Generate query embedding
            query_embedding = self.embedding_model.embed_query(query)
            query_embedding = np.array([query_embedding], dtype=np.float32)
            faiss.normalize_L2(query_embedding)
            
            # Search
            scores, indices = self.index.search(query_embedding, min(k, len(self.documents)))
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                idx = int(idx)
                if idx >= 0 and idx < len(self.documents):
                    document = self.documents[idx]
                    results.append({
                        'text': document['text'],
                        'filename': document['filename'],
                        'pdf_id': document['pdf_id'],
                        'chunk_id': document['chunk_id'],
                        'chunk_index': document['chunk_index'],
                        'score': float(score)
                    })
            
            return results
    
    def get_pdf_info(self, pdf_id):
        """Get information about a specific PDF"""
        return self.pdf_registry.get(pdf_id)
    
    def list_pdfs(self):
        """List all PDFs in the vector store"""
        return self.pdf_registry
    
    def remove_pdf(self, pdf_id):
        """Remove a PDF and its associated file from the vector store"""
        if pdf_id not in self.pdf_registry:
            return False
        
        # Remove the PDF file
        pdf_file_path = self._get_pdf_file_path(pdf_id)
        if os.path.exists(pdf_file_path):
            try:
                os.remove(pdf_file_path)
            except Exception as e:
                st.error(f"Error removing PDF file: {str(e)}")
                return False
        
        # Remove from registry
        del self.pdf_registry[pdf_id]
        
        # Save updated registry
        self._save_registry()
        
        # Rebuild combined index
        self._rebuild_combined_index()
        
        return True
    
    def save(self, filepath=None):
        """Save vector store registry (individual PDFs are already saved separately)"""
        # This method now primarily saves the registry since PDFs are saved individually
        self._save_registry()
    
    def load(self, filepath=None):
        """Load vector store from individual PDF files"""
        # Load the registry
        self._load_registry()
        
        # Rebuild the combined index from all PDF files
        self._rebuild_combined_index()
        
        return len(self.pdf_registry) > 0


def load_embedding_model():
    """Load the Google Generative AI embedding model"""
    return GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL)


def get_vector_store():
    """Get or create vector store"""
    embedding_model = load_embedding_model()
    vector_store = VectorStore(embedding_model)
    vector_store.load()
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
            # No need to call save() as it's handled automatically in add_documents

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
