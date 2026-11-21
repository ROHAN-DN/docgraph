FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY prompts ./prompts

RUN python -m pip install --no-cache-dir .

EXPOSE 8000 8501
CMD ["uvicorn", "docgraph.api:app", "--host", "0.0.0.0", "--port", "8000"]
