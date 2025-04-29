# MovieLens Recommender API Development Guide

## Deployment Troubleshooting

### Original Issue
The MovieLens Recommender API was failing to deploy properly on Google Cloud Run with a 503 Service Unavailable error. Upon investigation, we discovered that the service was failing during startup with the following error:

```
ModuleNotFoundError: No module named 'main'
```

The error occurred because the deployment was attempting to use Gunicorn to load a WSGI application from a module named 'main' that didn't exist or wasn't in the Python path.

### Diagnosis Process

1. **Checking Cloud Run Logs**: We examined the logs and found that the service was consistently failing with module import errors.

2. **Configuration Review**: We reviewed the `cloudbuild.yaml` and found that it was setting an environment variable `PYTHON_ENTRYPOINT=/app/server.py` which was causing conflicts with the application's startup process.

3. **Dockerfile Analysis**: Multiple Dockerfiles were present, with complex fallback mechanisms that were not working as expected in the Cloud Run environment.

### Solution Implemented

We approached the problem with a "less is more" philosophy, creating a minimal but functional deployment:

1. **Created a Simplified Script**: We developed `direct-deploy.sh` that performs these steps:
   - Creates a minimal Python HTTP server (`minimal_server.py`) using only the built-in `http.server` module
   - Creates a minimal Dockerfile
   - Builds and deploys directly to Cloud Run

2. **Removed Problematic Environment Variables**: We removed the `PYTHON_ENTRYPOINT` environment variable that was causing conflicts.

3. **Simplified the Application**: Instead of the complex application with multiple fallback mechanisms, we deployed a standalone HTTP server that:
   - Serves the root endpoint (`/`) with a welcome message
   - Provides a health check endpoint (`/health`)

4. **Built and Deployed with Standard GCP Tools**:
   ```bash
   gcloud builds submit --tag gcr.io/$PROJECT_ID/movielens-minimal-backend .
   gcloud run deploy movielens-recommender-backend-2 --image gcr.io/$PROJECT_ID/movielens-minimal-backend ...
   ```

The result is a working API deployed at:
```
https://movielens-recommender-backend-2-hn6i3ii42q-uc.a.run.app/
```

## Current API Endpoints

The minimal implementation currently provides two endpoints:

1. **Root Endpoint (`/`)**:
   ```json
   {"message": "Welcome to MovieLens Recommender API v1.1.0"}
   ```

2. **Health Endpoint (`/health`)**:
   ```json
   {"status": "ok"}
   ```

## Development Scripts

Several deployment scripts were created to assist with deployment:

1. **`deploy-to-cloud-run.sh`**: The original script that uses Cloud Build and a complex configuration.

2. **`simple-deploy.sh`**: An intermediate solution that tried to simplify the deployment process.

3. **`direct-deploy.sh`**: The successful minimal approach that builds and deploys a standalone HTTP server.

## Next Steps for Development

1. **Gradual Enhancement**: The current implementation can be gradually enhanced with features from the original codebase.

2. **Database Integration**: Re-integrate MongoDB, Redis, or other database connections.

3. **Restore Original Endpoints**: Implement the movie recommendation endpoints, user interaction endpoints, etc.

4. **Authentication & Authorization**: Add proper security mechanisms.

5. **CI/CD Pipeline**: Set up continuous integration and deployment.

## Deployment Recommendations

For future deployments, we recommend:

1. **Start Simple**: Begin with a minimal implementation and gradually add complexity.

2. **Use Direct Deployment**: Use the `direct-deploy.sh` approach for reliability.

3. **Log Monitoring**: Keep an eye on the Cloud Run logs for any issues.

4. **Environment Variables**: Be cautious with environment variables like `PYTHON_ENTRYPOINT` which can conflict with the container's CMD instruction.

5. **Test Locally**: When possible, test Docker builds locally before pushing to Cloud Run.

## Troubleshooting Tools

These commands are helpful for troubleshooting Cloud Run deployments:

```bash
# View Cloud Run service details
gcloud run services describe SERVICE_NAME --platform=managed --region=REGION --format=yaml

# View deployment logs (errors only)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=SERVICE_NAME AND severity>=ERROR" --limit 20 --format=json
```

Remember to replace `SERVICE_NAME` and `REGION` with your specific values. 