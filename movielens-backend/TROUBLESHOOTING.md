# Troubleshooting Guide

This guide provides solutions for common issues encountered when deploying the MovieLens Recommender API to Google Cloud Run.

## Common Deployment Issues

### ModuleNotFoundError: No module named 'main'

This error occurs when the Python interpreter can't find the main.py module when the container starts.

**Possible causes:**
1. The PYTHONPATH environment variable is not set correctly
2. main.py is not in the expected location
3. The working directory is not set correctly

**Solutions:**
1. **Use the alternative Docker deployment:**
   - Our deployment now uses a more robust approach with Dockerfile.alternative
   - This sets the correct PYTHONPATH and uses a fallback mechanism

2. **Check the logs:**
   - Look for the output from startup_check.py which shows:
     - Current directory
     - Python path
     - File existence
     - Module path resolution

3. **Manual fix (if needed):**
   - Deploy a new revision with these Cloud Run settings:
     ```
     --set-env-vars=PYTHONPATH=/app
     ```

### Container fails to start

If the container fails to start entirely, check the logs in Cloud Run for errors.

**Possible causes:**
1. Missing dependencies
2. Configuration errors
3. Memory/resource limitations

**Solutions:**
1. **Check requirements.txt:**
   - Ensure all dependencies are correctly specified
   - Make sure version constraints are not too restrictive

2. **Increase resource allocation:**
   - Update the deployment with more memory
     ```
     --memory=1Gi
     ```

3. **Simplify the application:**
   - Use main_simple.py which has minimal dependencies

### API returns "Service Unavailable"

If you can access some endpoints but others return "Service Unavailable", there may be issues with specific routes.

**Possible causes:**
1. Internal server errors
2. Timeouts
3. Database connection issues

**Solutions:**
1. **Check specific endpoint logs:**
   - Look for errors related to the failing endpoints

2. **Increase timeout settings:**
   - Update the deployment with a longer timeout
     ```
     --timeout=600s
     ```

3. **Check database connections:**
   - Verify that all database connections are properly configured
   - Check if environment variables for database access are set

## Debugging Tools

1. **startup_check.py**: Runs at container startup to diagnose the environment
   - Lists the Python path
   - Shows files in the current directory
   - Checks if key modules can be imported

2. **run.py**: Alternative entry point that handles import issues
   - Sets the Python path explicitly
   - Provides detailed logging
   - Falls back to a simplified app if the main app fails

3. **main_simple.py**: Simplified version of the application
   - Minimal dependencies
   - Basic endpoints for diagnostics

## Viewing Logs

To view logs in Google Cloud Run:

1. Go to the Google Cloud Console
2. Navigate to Cloud Run > [your-service]
3. Click on "Logs" tab
4. Filter logs by severity or text

Alternatively, use the gcloud CLI:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=movielens-recommender-backend" --limit=50
```

## Getting Additional Help

If you continue to experience issues:

1. Check the GitHub issue tracker
2. Review the deployment documentation
3. Try deploying the simplified version directly:
   ```bash
   cp main_simple.py main.py
   git add main.py
   git commit -m "Use simplified main.py for debugging"
   git push origin main
   ``` 