FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN ls -la /app/src/ && python -c "import sys; sys.path.insert(0,'/app'); from src.api.server import app; print('import OK')"

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8080

CMD PYTHONPATH=/app python -c "from src.api.server import app; import uvicorn,os; uvicorn.run(app,host='0.0.0.0',port=int(os.environ.get('PORT',8080)))"
