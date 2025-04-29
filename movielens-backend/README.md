# MovieLens Recommender API

A FastAPI-based recommendation system for MovieLens dataset, deployed on Google Cloud Run.

## Continuous Deployment with GitHub Actions

This project is configured for continuous deployment using GitHub Actions. Whenever changes are pushed to the `main` branch, the application is automatically built and deployed to Google Cloud Run.

### Setting Up GitHub Secrets

Before the GitHub Actions workflow can deploy to Cloud Run, you need to set up the following secrets in your GitHub repository:

1. Go to your GitHub repository.
2. Navigate to Settings > Secrets and variables > Actions.
3. Add the following secrets:

   - `GCP_PROJECT_ID`: Your Google Cloud Project ID
   - `GCP_SA_KEY`: The JSON key of a service account with the following roles:
     - Cloud Run Admin
     - Storage Admin
     - Service Account User

### Creating a Service Account Key

1. In Google Cloud Console, go to IAM & Admin > Service Accounts.
2. Create a new service account or select an existing one.
3. Grant the required roles:
   - Cloud Run Admin
   - Storage Admin
   - Service Account User
4. Create a JSON key for this service account.
5. Copy the entire content of the JSON key file and add it as the `GCP_SA_KEY` secret in GitHub.

## Module Import Issues in Cloud Run

If you encounter a "ModuleNotFoundError: No module named 'main'" error in Cloud Run, we've implemented the following solutions:

1. **Enhanced Dockerfile**: Our deployment now uses a more robust approach that properly sets the Python path.

2. **Alternative Entry Point**: We've created a `run.py` script that handles Python path issues and can fall back to a simplified version if needed.

3. **Diagnostic Tools**: The deployment includes:
   - `startup_check.py` to diagnose environment issues
   - `main_simple.py` as a fallback implementation with minimal dependencies

These changes ensure that the application can start even if there are issues with the Python module path in Cloud Run.

## Local Development

### Prerequisites

- Python 3.10+
- Docker (optional)

### Setup

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy the sample environment file:
   ```
   cp .env.sample .env
   ```
   Then edit `.env` to configure your environment.

### Running Locally

Run the FastAPI application:

```bash
uvicorn main:app --reload
```

### Using Docker

Build and run the Docker container:

```bash
docker build -t movielens-recommender .
docker run -p 8080:8080 movielens-recommender
```

## API Documentation

When the application is running, documentation is available at:
- Swagger UI: `/docs`
- ReDoc: `/redoc` 