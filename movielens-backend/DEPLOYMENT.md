# Deployment Guide for MovieLens Recommender API

This guide walks you through the process of setting up continuous deployment for the MovieLens Recommender API using GitHub Actions and Google Cloud Run.

## Prerequisites

- A GitHub account
- A Google Cloud Platform (GCP) account
- The `gcloud` CLI installed locally (for initial setup only)

## Step 1: Configure Google Cloud Platform

1. **Create a Google Cloud Project** (if you don't have one already)
   ```bash
   gcloud projects create your-project-id --name="MovieLens Recommender"
   gcloud config set project your-project-id
   ```

2. **Enable Required APIs**
   ```bash
   gcloud services enable cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com
   ```

3. **Create a Service Account for GitHub Actions**
   ```bash
   gcloud iam service-accounts create github-actions-deployer \
     --description="Service account for GitHub Actions to deploy to Cloud Run" \
     --display-name="GitHub Actions Deployer"
   ```

4. **Grant the Required Permissions**
   ```bash
   # Cloud Run Admin role
   gcloud projects add-iam-policy-binding your-project-id \
     --member="serviceAccount:github-actions-deployer@your-project-id.iam.gserviceaccount.com" \
     --role="roles/run.admin"
   
   # Storage Admin role (for container registry)
   gcloud projects add-iam-policy-binding your-project-id \
     --member="serviceAccount:github-actions-deployer@your-project-id.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   
   # Service Account User role (to allow deploying to Cloud Run)
   gcloud projects add-iam-policy-binding your-project-id \
     --member="serviceAccount:github-actions-deployer@your-project-id.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"
   ```

5. **Create and Download a JSON Key**
   ```bash
   gcloud iam service-accounts keys create github-actions-key.json \
     --iam-account=github-actions-deployer@your-project-id.iam.gserviceaccount.com
   ```

## Step 2: Configure GitHub Repository

1. **Add the Service Account Key as a GitHub Secret**
   - Go to your GitHub repository
   - Navigate to Settings > Secrets and variables > Actions
   - Click "New repository secret"
   - Name: `GCP_SA_KEY`
   - Value: *Copy and paste the contents of the github-actions-key.json file*
   - Click "Add secret"

2. **Add Your Google Cloud Project ID as a Secret**
   - Again, click "New repository secret"
   - Name: `GCP_PROJECT_ID`
   - Value: *Your Google Cloud project ID*
   - Click "Add secret"

## Step 3: Verify GitHub Actions Workflow

1. Our GitHub Actions workflow file (`.github/workflows/cloud-run-deploy.yml`) is already set up to:
   - Trigger on pushes to the `main` branch
   - Build the Docker container
   - Deploy to Google Cloud Run

2. You can also manually trigger a deployment:
   - Go to your GitHub repository
   - Click on the "Actions" tab
   - Select the "Deploy to Cloud Run" workflow
   - Click "Run workflow"

## Step 4: Make a Change and Deploy

1. Make a change to your code
2. Commit and push to the `main` branch
   ```bash
   git add .
   git commit -m "Update application"
   git push origin main
   ```
3. The GitHub Actions workflow will automatically start
4. Go to the "Actions" tab in your GitHub repository to monitor the deployment

## Step 5: Verify the Deployment

1. Once the deployment is complete, GitHub Actions will output the service URL
2. Access the URL to check if your application is running properly
3. You can also check the status in the Google Cloud Console:
   - Go to Cloud Run in the console
   - You should see your service running with the latest revision

## Troubleshooting

- **Deployment fails with permission errors**:
  - Verify the service account has the correct roles
  - Check that the secrets in GitHub are correctly set up
  
- **Container fails to start**:
  - Check the Cloud Run logs for errors
  - Verify that your `Dockerfile` is correctly set up

- **API returns "Service Unavailable"**:
  - Check if the service has started properly in Cloud Run
  - Look at the logs for any startup errors 