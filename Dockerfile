FROM python:3.12-slim
WORKDIR /app
COPY app app
COPY static static
ENV PORT=8000 SANDBOX_BACKEND=docker
EXPOSE 8000
CMD ["python3", "-m", "app.server"]
