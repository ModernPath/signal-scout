FROM python:3.12.7-slim-bookworm

WORKDIR /agent
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
RUN useradd --create-home --uid 10002 intelligence
USER intelligence

CMD ["python", "signal_intelligence.py", "--chat"]
