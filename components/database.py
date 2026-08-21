import psycopg2 
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai  import ChatGoogleGenerativeAI
from components import OpenRouterRerank, GeminiEmbeddings, load_and_split_pdf

import os 
from dotenv import load_dotenv

gemini_embeddings = GeminiEmbeddings()
reranker = OpenRouterRerank(api_key=OPENROUTER_API_KEY)

def insert_into_database(pdf_path: str):
    conn = psycopg2.connect(
        database="vectordb3",
        user="postgres",
        password="newpassword",  
        host="127.0.0.1",
        port=5432
    )
    cursor = conn.cursor()

    docs_list, parent_docs_list, child_docs_list, child_texts = (load_and_split_pdf(pdf_path)) 
    embedded_contents = gemini_embeddings.embed_documents(child_texts)
    
    doc = docs_list[0]

    pdf_id = doc.metadata["document_id"]
    pdf_name = doc.metadata["pdf_name"]

    cursor.execute(
        """
        INSERT INTO documents (file_hash, pdf_name)
        VALUES (%s, %s)
        ON CONFLICT (file_hash) DO NOTHING
        """,
        (pdf_id, pdf_name)
    )
    conn.commit()

    for parent_doc in parent_docs_list:
        parent_docs_id = parent_doc.metadata["parent_id"] 
        hash_id = parent_doc.metadata["document_id"] 
        parent_pages = parent_doc.metadata["page"]  #mark where the page number is coming from
        parent_texts = parent_doc.page_content 
        cursor.execute(
            "INSERT INTO parent_chunks (parent_id, file_hash, page, parent_texts) VALUES (%s,%s,%s,%s) ON CONFLICT (parent_id) DO NOTHING", 
            (str(parent_docs_id), hash_id, parent_pages, parent_texts)
            )
    conn.commit()

    for child_doc, embedded_content in zip(child_docs_list, embedded_contents):
        child_id = child_doc.metadata["child_id"]
        child_parent_id = child_doc.metadata["parent_id"]
        child_text = child_doc.page_content
        embedding = embedded_content
        cursor.execute(
            "INSERT INTO  child_chunks (child_id, parent_id, child_text, embeddings) VALUES (%s,%s,%s,%s) ON CONFLICT (child_id) DO NOTHING", 
            (str(child_id), str(child_parent_id), child_text, embedding)
        )
    conn.commit()


def query_database(query):

    conn = psycopg2.connect(
        database="vectordb3",
        user="postgres",
        password="newpassword",  # <-- Change this from "password"
        host="127.0.0.1",
        port=5432
    )
    cursor = conn.cursor()    

    embed_query = str(gemini_embeddings.embed_query(query))
  

    sql_query = """ 
    WITH ranked_child_chunks AS ( 
        SELECT parent_id, (embeddings <=> %s::vector ) AS distance FROM child_chunks 
        ORDER BY embeddings <=> %s::vector ASC
        LIMIT 20
    ),

    deduplicated_parent_ids AS (
        SELECT  parent_id , MIN(distance) as best_distance from ranked_child_chunks
        GROUP BY parent_id
    )

    SELECT p.parent_id, p.parent_texts, p.page FROM parent_chunks p
    JOIN deduplicated_parent_ids d on p.parent_id = d.parent_id
    WHERE length(p.parent_texts) > 100 
    ORDER BY d.best_distance ASC
    LIMIT 5 
    """
    cursor.execute(sql_query, (embed_query, embed_query))

    sql_result = cursor.fetchall()
    

    documents_payload = [
        {"text": result[1]} for result in sql_result
    ]

    
    results = reranker.rerank(query=query, documents=documents_payload, top_n=1)
    context = [result.get('source') for result in results]

    llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    api_key=api_key,
    )

    system_prompt = "You are an expert technical writer. Answer using bullet points'"
    user_content = f"""Context:
    {context}

    Question:
    {query}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content)
    ])
    return response.content