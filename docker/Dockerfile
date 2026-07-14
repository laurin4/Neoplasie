FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Runtime writable dirs (git-ignored; never bake in patient data).
RUN mkdir -p /app/data/raw /app/data/outputs

# Run the pipeline explicitly, e.g.:
#   docker run --rm -v $PWD/data:/app/data <image> \
#     python3 -m src.tasks.tumor_histopathology.run_pipeline --input data/raw/input.xlsx
CMD ["bash"]
