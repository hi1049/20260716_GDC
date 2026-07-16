# ====================================================================
# GridPulse 단일 컨테이너 클라우드 배포용 Dockerfile (Cloud Run 최적화)
# ====================================================================

FROM python:3.12-slim

# 작업 디렉토리 지정
WORKDIR /app

# requirements.txt 복사 및 종속성 패키지 설치 (Vertex AI / ADC 지원 포함)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드를 복사합니다
COPY main.py /app/main.py
COPY backup.csv /app/backup.csv
COPY .env /app/.env
COPY static/ /app/static/

# Cloud Run 기본 권장 포트 노출 (8080)
EXPOSE 8080

# uvicorn을 이용하여 백엔드와 프론트엔드를 동시 기동합니다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
