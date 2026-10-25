FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ELUNO_RUNTIME=/data ELUNO_SECURE_COOKIES=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY exercise-pack/starter-kit ./exercise-pack/starter-kit
COPY run_demo.py .
RUN useradd --create-home demo && mkdir /data && chown demo:demo /data
USER demo
EXPOSE 8000
CMD ["python", "run_demo.py", "--host", "0.0.0.0"]
