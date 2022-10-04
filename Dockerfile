FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY impf.py impf.py
COPY byimpf byimpf

ENTRYPOINT ["python", "impf.py"]
