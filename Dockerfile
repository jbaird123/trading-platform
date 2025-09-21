# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy the dependency files to the working directory
COPY pyproject.toml poetry.lock ./

# Install project dependencies
RUN poetry install --no-root

# Copy the rest of the application's source code from the host to the container
COPY . .

# Make the `src` directory available to Python
ENV PYTHONPATH="${PYTHONPATH}:/app/src"
