FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "4_假逻辑换成真AI:app", "--host", "0.0.0.0", "--port", "8000"]
