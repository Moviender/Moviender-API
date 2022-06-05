FROM python:3.9

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . .

ARG service_account_key_path=/code/serviceAccountKey.json

ENV GOOGLE_APPLICATION_CREDENTIALS=$service_account_key_path

CMD ["uvicorn", "moviender-app.main:app", "--host", "0.0.0.0", "--port", "8000"]