import sys

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings.bedrock import BedrockEmbeddings
from langchain_community.vectorstores import FAISS


def load_and_split_pdfs(
    pdf_dir: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
):
    """
    Load PDFs from a directory and split them into chunks.
    """
    loader = PyPDFDirectoryLoader(pdf_dir)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = splitter.split_documents(docs)
    return chunks



