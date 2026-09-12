import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from components.database import search_parent_chunks
from components.env import load_project_env
from components.graph import graph_overview, merge_graph

load_project_env()

GRAPH_EXTRACT_PROMPT = """คุณสกัดกราฟความรู้สำหรับ Neo4j
ตอบเป็น JSON อย่างเดียว ไม่มีคำอธิบาย ไม่มี markdown

รูปแบบ:
{"nodes":[{"name":"Hypertension","thai":"ความดันโลหิตสูง","kind":"disease","definition":"อธิบาย 2-4 ประโยค"}],"relationships":[{"from":"Hypertension","to":"Stroke","type":"INCREASES_RISK","label":"เพิ่มความเสี่ยง","detail":"อธิบายว่าทำไมจึงเชื่อมกัน"}]}

กฎ:
- ใช้เฉพาะข้อมูลจากข้อความผู้ใช้และ context เอกสาร
- อย่าแต่งโหนดที่ไม่มีในข้อมูล
- definition ของแต่ละโหนดต้องละเอียด 2-4 ประโยค บอกความหมายและบริบทการใช้
- relationships ใส่ detail อธิบายเหตุผลของเส้นเชื่อม
- kind ใช้หนึ่งใน: disease, concept, symptom, sign, prefix, suffix, procedure, abbreviation, term
- type ใช้ตัวพิมพ์ใหญ่คั่นด้วยขีดล่าง
- ไม่เกิน 20 โหนด และ 25 ความสัมพันธ์
- name ใช้คำต้นฉบับที่สั้น ชัด
"""


def _parse_graph_payload(text: str) -> dict:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        raw = match.group(0)
    data = json.loads(raw)
    nodes = []
    for item in data.get("nodes") or []:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        nodes.append(
            {
                "name": name,
                "thai": str(item.get("thai") or "").strip(),
                "kind": str(item.get("kind") or "term").strip() or "term",
                "definition": str(item.get("definition") or "").strip(),
            }
        )
    relationships = []
    for item in data.get("relationships") or []:
        from_name = str(item.get("from") or "").strip()
        to_name = str(item.get("to") or "").strip()
        if not from_name or not to_name:
            continue
        rel_type = str(item.get("type") or "RELATED_TO").strip() or "RELATED_TO"
        relationships.append(
            {
                "from": from_name,
                "to": to_name,
                "type": rel_type,
                "label": str(item.get("label") or rel_type).strip() or rel_type,
                "detail": str(item.get("detail") or "").strip(),
            }
        )
    return {"nodes": nodes[:20], "relationships": relationships[:25]}


def build_graph_from_prompt(query: str) -> dict:
    rows = search_parent_chunks(query)
    context = [row[1] for row in rows[:3]]
    source_name = next((row[3] for row in rows if row[3]), None) or "chat-graph"
    sources = [
        {
            "page": row[2],
            "text": row[1],
            "filename": row[3],
            "document_id": row[4],
        }
        for row in rows
    ]

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )
    user_content = f"""คำสั่งผู้ใช้:
{query}

Context จากเอกสาร:
{context or "ไม่มีเอกสารที่เกี่ยวข้อง ใช้เฉพาะคำสั่งผู้ใช้"}"""
    response = llm.invoke(
        [
            SystemMessage(content=GRAPH_EXTRACT_PROMPT),
            HumanMessage(content=user_content),
        ]
    )
    try:
        extracted = _parse_graph_payload(response.content)
    except Exception:
        return {
            "answer": "สกัดกราฟจากข้อความไม่สำเร็จ ลองระบุศัพท์และความสัมพันธ์ให้ชัดขึ้น",
            "sources": sources,
            "graph": [],
            "overview": graph_overview(),
            "written": {"nodes": 0, "relationships": 0, "skipped": True},
        }

    if not extracted["nodes"]:
        return {
            "answer": "ยังไม่พบศัพท์ที่ชัดพอจะสร้างกราฟ ลองระบุชื่อโหนดและความสัมพันธ์ เช่น Hypertension เพิ่มความเสี่ยง Stroke",
            "sources": sources,
            "graph": [],
            "overview": graph_overview(),
            "written": {"nodes": 0, "relationships": 0, "skipped": True},
        }

    written = merge_graph(extracted["nodes"], extracted["relationships"], source_name)
    if written.get("skipped"):
        return {
            "answer": "เชื่อม Neo4j ไม่ได้ เปิด Docker แล้วลองอีกครั้ง",
            "sources": sources,
            "graph": [],
            "overview": graph_overview(),
            "written": written,
        }

    overview = graph_overview()
    facts = [
        {
            "name": node["name"],
            "thai": node.get("thai", ""),
            "kind": node.get("kind", ""),
            "definition": node.get("definition", ""),
        }
        for node in extracted["nodes"]
    ]
    for rel in extracted["relationships"]:
        facts.append(
            {
                "name": rel["from"],
                "relation": f"{rel['from']} -[{rel.get('label') or rel['type']}]-> {rel['to']}",
                "related_name": rel["to"],
                "relation_detail": rel.get("detail", ""),
            }
        )
    node_lines = []
    for node in extracted["nodes"]:
        title = node["name"]
        if node.get("thai"):
            title += f" ({node['thai']})"
        node_lines.append(f"- {title}: {node.get('definition') or 'ศัพท์ในกราฟ'}")
    rel_lines = []
    for rel in extracted["relationships"]:
        label = rel.get("label") or rel["type"]
        line = f"- {rel['from']} — {label} → {rel['to']}"
        if rel.get("detail"):
            line += f"\n  {rel['detail']}"
        rel_lines.append(line)
    answer = (
        f"บันทึกกราฟจาก {source_name} แล้ว {written['nodes']} โหนด และ {written['relationships']} ความสัมพันธ์\n\n"
        f"โหนดที่เพิ่มหรืออัปเดต:\n"
        f"{chr(10).join(node_lines) or '- ไม่มี'}\n\n"
        f"ความสัมพันธ์:\n"
        f"{chr(10).join(rel_lines) or '- ไม่มีเส้นเชื่อมใหม่'}"
    )
    return {
        "answer": answer,
        "sources": sources,
        "graph": facts,
        "overview": overview,
        "written": written,
    }
