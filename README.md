# Medical RAG AI

ระบบถามเอกสารทางการแพทย์แบบ Parent-Child RAG  
อัปโหลด PDF หรือ CSV แล้วถามผ่านแชท ค้นจากคลังเอกสารทั้งหมด และดูกราฟศัพท์ใน Neo4j

- หน้าบ้าน: Next.js ที่ [http://localhost:3000](http://localhost:3000)
- หลังบ้าน: FastAPI ที่ [http://127.0.0.1:8000](http://127.0.0.1:8000)
- ฐานข้อมูล: Postgres + pgvector และ Neo4j ผ่าน Docker

## สิ่งที่ต้องมีก่อนรัน

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python 3.11+
- Node.js 20+
- คีย์ API
  - `GOOGLE_API_KEY` สำหรับ Gemini embedding
  - `OPENAI_API_KEY` สำหรับตอบแชทและสร้างกราฟ
  - `OPENROUTER_API_KEY` สำหรับ rerank (ถ้ามี)

## 1) ตั้งค่า environment

คัดลอกตัวอย่างแล้วใส่คีย์ของตัวเอง อย่า commit ไฟล์ `.env`

```bash
cp .env.example .env
```

บน PowerShell:

```powershell
Copy-Item .env.example .env
```

ค่าฐานข้อมูลใน `.env.example` ตรงกับ `docker-compose.yml` อยู่แล้ว

## 2) เปิดฐานข้อมูล

เปิด Docker Desktop แล้วรันที่รากโปรเจกต์

```bash
docker compose up -d
```

บริการที่ขึ้น:

| บริการ | พอร์ต | บัญชีตั้งต้น |
|---|---|---|
| Postgres + pgvector | `5432` | `postgres` / `newpassword` ฐาน `vectordb3` |
| Neo4j | `7474` (เบราว์เซอร์), `7687` (Bolt) | `neo4j` / `newpassword` |

ตรวจว่าคอนเทนเนอร์ทำงาน:

```bash
docker compose ps
```

## 3) รันหลังบ้าน (FastAPI)

ที่รากโปรเจกต์:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

รัน API จากโฟลเดอร์ `backend` หลัง activate venv แล้ว:

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000 --host 127.0.0.1
```

หรือรันจากรากโปรเจกต์โดยไม่ต้องเข้า `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000 --host 127.0.0.1
```

ตรวจว่าหลังบ้านขึ้นแล้ว: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

อย่ารันคำสั่ง `.\.venv\Scripts\python.exe` ตอนอยู่ในโฟลเดอร์ `backend` เพราะ venv อยู่ที่รากโปรเจกต์

## 4) รันหน้าบ้าน (Next.js)

เปิดเทอร์มินัลอีกอัน:

```powershell
cd frontend
npm install
npm run dev
```

เปิด [http://localhost:3000](http://localhost:3000)

หน้าบ้านยิง API ผ่าน `/rag/*` แล้ว rewrite ไปที่ `http://127.0.0.1:8000`  
ถ้าหลังบ้านอยู่คนละเครื่องหรือคนละพอร์ต ตั้ง `RAG_API_URL` ใน `frontend/.env.local`

## ลำดับที่แนะนำตอนเปิดเครื่องใหม่

1. เปิด Docker Desktop
2. `docker compose up -d`
3. รันหลังบ้านที่พอร์ต `8000`
4. รันหน้าบ้านที่พอร์ต `3000`
5. เปิดเว็บที่ `http://localhost:3000`

## วิธีใช้คร่าวๆ

1. แทบ **อัปโหลด** ใส่ไฟล์ PDF หรือ CSV
2. แทบ **Dataset** ดูสรุปคลังที่ index แล้ว
3. แทบ **Chat** ถามจากเอกสารทั้งหมดที่เคยอัป
4. ปุ่มกราฟเปิดแผง Neo4j หรือใช้โหมดสร้างกราฟจากข้อความ

ไฟล์ต้นฉบับถูกอ่านแล้วทิ้ง ระบบเก็บเฉพาะช่วงข้อความและเวกเตอร์ใน Postgres

## โครงสร้างหลัก

```text
backend/main.py              API FastAPI
frontend/                    UI Next.js
components/database.py       อัปโหลด ค้นหา ตอบแชท
components/chunking_process.py  หั่น PDF / CSV แบบ parent-child
components/gemini_embedding.py  ฝังเวกเตอร์ด้วย Gemini
components/graph.py          Neo4j
docker-compose.yml           Postgres และ Neo4j
```

