from openai import AsyncOpenAI
import os
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from typing import Optional, List
from dotenv import load_dotenv
import asyncio
from fastapi.responses import StreamingResponse,FileResponse

from fastapi.security import APIKeyHeader
from fastapi import Depends
from torchgen.gen_functionalization_type import return_str
from sqlalchemy.orm import Session
from database import SessionLocal, ChatRecord
import urllib.parse
env_path = r"D:\PythonProject3\key.env"
load_dotenv(dotenv_path=env_path)
print(f"正在尝试加载配置文件：{env_path}")
print(f"调试读到的Key是：{os.getenv('OPENAI_API_KEY')}")
print(f"调试读到的Base URL是：{os.getenv('OPENAI_BASE_URL')}")
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)
# image_client = AsyncOpenAI(
#     api_key="",
#     base_url = ""
# )
api_key_header = APIKeyHeader(name="X-API-Key")
async def verify_api_key(api_key: str = Depends(api_key_header)):
    real_key = os.getenv("MY_API_KEY")
    if real_key!=api_key:
        raise HTTPException(status_code=401,detail="无效的 API 密钥")
app = FastAPI(title="我的第一个 AI 助手 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（比如你的 HTML 文件）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法（包括 OPTIONS, POST 等）
    allow_headers=["*"],  # 允许所有请求头
)
class message(BaseModel):
    role: str
    content: str
class AIQuery(BaseModel):
    prompt: str = Field(..., min_length=1,str_strip=True,description="用户的提问内容",)
    max_tokens: int = 100
    temperature: float = Field(0.7, ge=0, le=2)
    history:list = []
# db: Session = Depends(get_db)
# def get_db():
#     db = SessionLocal()# 1. 找前台拿通行证
#     try:
#         yield db# 2. 把通行证借给后面的路由函数去用
#     finally:
#         db.close()# 3. 无论怎样，最后一定要归还通行证、关门
@app.post("/chat")
async def chat_with_ai(query: AIQuery,api_key: str = Depends(verify_api_key)):
    db=SessionLocal()
    user_msg = ChatRecord(role="user", content=query.prompt)
    db.add(user_msg)
    db.commit()
    try:
        messages = [
            {"role": "system", "content": """你是一个拥有10年经验..."""}
        ]
        messages.extend(query.history)
        #messages = [{"role":m.role,"content":m.content} for m in query.history]
        messages.append({"role":"user","content":query.prompt})
        if "画" in query.prompt:
            print("📍 [监控 1] 成功进入画图通道！准备呼叫 API...")
            # response = await client.images.generate(
            #     model = "black-forest-labs/FLUX.1-schnell",
            #     prompt = query.prompt,
            #     size = "1024x1024"
            # )
            # image_url = response.data[0].url

            encoded_prompt = urllib.parse.quote(query.prompt)
            image_url = f"https://placehold.co/600x400/png?text={encoded_prompt}"

            # image_url = "https://picsum.photos/400/400"

            image_markdown = f"![生成的图片]({image_url})"
            print("📍 [监控 2] API 调用完成！画师已交稿！")
            async def generate_image_chunk():
                yield image_markdown
            return StreamingResponse(generate_image_chunk(), media_type="text/plain")
        else:
            async def generate_chunks():
                response = await client.chat.completions.create(
                    model = os.getenv("AI_MODEL_NAME", "deepseek-chat"),
                    messages=messages,
                    temperature=query.temperature,
                    timeout=20,
                    stream=True
                )
                full_ai_response = ""
                async for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        full_ai_response = full_ai_response + content
                        yield content
                try:
                    background_db = SessionLocal()
                    ai_msg = ChatRecord(role="assistant", content=full_ai_response)
                    background_db.add(ai_msg)
                    background_db.commit()
                finally:
                    background_db.close()

            return StreamingResponse(generate_chunks(), media_type="text/plain")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="AI 服务器响应超时，请稍后再试")
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"AI 大脑突然短路了：{str(e)}")
    finally:
        db.close()
@app.get("/history")
async def get_chat_history():
#在函数里声明会话  db:Session = Depends(get_db) 不用在async def get_chat_history()的括号里注入依赖
    db=SessionLocal()
    try:
        records = db.query(ChatRecord).all()
        history_list = [] #也可以写成 history_list=[{"user": record.user_message,"ai": record.ai_response}for record in records]
        for record in records:#直接写列表推导式可以不用提前声明一个空列表
            history_list.append({
                "role": record.role,
                "content":record.content
            })
        return history_list
    finally:
        db.close()
@app.delete("/clear")
async def clear_chat_history():
    db =SessionLocal()
    try:
        db.query(ChatRecord).delete()
        db.commit()
        return {"message":"记忆已经彻底删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"相处记忆失败{str(e)}")
    finally:
        db.close()
@app.get("/")
async def get_homepage():
    return FileResponse("./index.html")
