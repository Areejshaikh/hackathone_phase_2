FROM python:3.9

# User setup (Hugging Face ki requirement hai)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

WORKDIR /app

# Requirements install karein
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Sara code copy karein
COPY --chown=user:user . .

# Port 7860 par backend start karein
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]