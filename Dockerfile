# ====================================================================
# VoltWise 단일 컨테이너 클라우드 배포용 Dockerfile
# ====================================================================

FROM python:3.12-slim

# 작업 디렉토리 지정
WORKDIR /app

# 시스템 의존성 및 Python 패키지 설치
RUN pip install --no-cache-dir fastapi uvicorn

# 애플리케이션 코드를 복사합니다
COPY main.py /app/main.py
COPY kpx_client.py /app/kpx_client.py
COPY scheduler_engine.py /app/scheduler_engine.py
COPY .env /app/.env
COPY static/ /app/static/

# Cloud Run 및 로컬 도커 포트 노출 (기본값 8000)
EXPOSE 8000

# uvicorn을 이용하여 백엔드와 프론트엔드를 동시 기동합니다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
