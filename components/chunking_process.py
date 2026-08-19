from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from pathlib import Path
import uuid
import hashlib



RAG_NAMESPACE = uuid.UUID('7d5a5286-6df7-4404-b97c-e0938f381c15')
def load_and_split_pdf(pdf_path: str):
    
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=30)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=20)
    docs_list = []
    child_docs_list = []
    parent_docs_list = []
    
   
    loader = PyPDFLoader(str(pdf_path))
    docs = loader.load()
        

        
    with open(pdf_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    document_id = file_hash
        
    for doc in docs:
        doc.metadata["pdf_name"] = pdf_path.name
        doc.metadata["document_id"] = document_id
    docs_list.extend(docs)

        
    parent_docs = parent_splitter.split_documents(docs)
    for parent_doc in parent_docs:
        parent_id = uuid.uuid5(RAG_NAMESPACE, parent_doc.page_content)
        parent_doc.metadata["parent_id"] = parent_id
    parent_docs_list.extend(parent_docs)
    
        
    for parent_doc in parent_docs:
        child_docs = child_splitter.split_documents([parent_doc])
        for child_doc in child_docs:
            child_id = uuid.uuid5(RAG_NAMESPACE, child_doc.page_content)
            child_doc.metadata["child_id"] = child_id
        child_docs_list.extend(child_docs)

    child_texts = [doc.page_content for doc in child_docs_list]

    return docs_list, parent_docs_list, child_docs_list, child_texts
    
    

