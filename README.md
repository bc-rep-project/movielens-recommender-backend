# MovieLens Recommender (GCP Free Tier)

<!-- Optional: Add badges for build status, license, etc. -->
<!-- [![Build Status](...)](...) -->
<!-- [![License: MIT](...)](...) -->

A content-based movie recommendation system built using the MovieLens dataset (`ml-latest-small`). This project is specifically designed and optimized to run primarily within the **free tiers** of various cloud services, with a focus on Google Cloud Platform (GCP) for the backend infrastructure.

The system ingests movie metadata, generates content embeddings using Hugging Face Sentence Transformers, stores data in MongoDB, handles user authentication via Supabase, processes user interactions (ratings/views), caches data with Redis, and serves recommendations via a FastAPI backend hosted on GCP Cloud Run. The frontend is built with Next.js and hosted on Vercel.

## Architecture Overview

The system follows a microservices-inspired approach, separating concerns:

1.  **Backend API (GCP Cloud Run):** A Python FastAPI application responsible for:
    *   Serving movie metadata.
    *   Handling user interaction submissions.
    *   Calculating and serving content-based recommendations (user-to-item & item-to-item).
    *   Authenticating users via Supabase JWTs.
    *   Interacting with databases and cache.
    *   **Optimized for Free Tier:** Configured with `minInstances: 0` to scale to zero when idle.
2.  **Frontend (Vercel):** A Next.js application providing the user interface for browsing movies, interacting, and viewing recommendations.
3.  **Database (MongoDB Atlas):** M0 Free Tier cluster storing:
    *   Movie metadata and pre-computed embeddings.
    *   User interaction logs.
    *   (Optional) Pre-computed recommendations or user profiles.
4.  **Authentication (Supabase):** Free Tier Supabase project handling user sign-up, login, and JWT token generation.
5.  **Cache (External Redis):** Free Tier Redis instance (e.g., Upstash, Render Redis) used for caching API responses, similarity results, and hot embeddings.
6.  **Storage (GCP Cloud Storage):** Standard GCS bucket used for:
    *   Caching the downloaded MovieLens dataset zip file (critical).
    *   Storing intermediate data processing files or simple model artifacts.
7.  **Offline Data Processing (GCP Cloud Functions/Workflows):** Python scripts, triggered manually or scheduled (e.g., via Cloud Scheduler), responsible for:
    *   Initial download and processing of the MovieLens dataset.
    *   Generating content embeddings using Sentence Transformers.
    *   Loading initial data into MongoDB.
    *   (Optional) Periodic updates or simple model retraining/pre-computation tasks.
    *   **Crucially runs *outside* the Cloud Run API service.**

<!-- Optional: Link to a diagram file -->
<!-- See [ARCHITECTURE.md](ARCHITECTURE.md) for a visual diagram. -->

## Technology Stack

*   **Backend:** Python, FastAPI
*   **Frontend:** Node.js, React, Next.js, TypeScript (optional)
*   **Cloud Provider:** Google Cloud Platform (GCP)
*   **Compute:** GCP Cloud Run (Backend API), GCP Cloud Functions (Gen 2 Recommended for Offline Tasks)
*   **Database:** MongoDB Atlas (M0 Free Tier)
*   **Authentication:** Supabase (Free Tier)
*   **Cache:** Redis (External Free Tier - e.g., Upstash, Render Redis, Aiven)
*   **Storage:** GCP Cloud Storage (GCS)
*   **Containerization:** Docker
*   **Embeddings:** Hugging Face `sentence-transformers` (e.g., `all-MiniLM-L6-v2`)
*   **Deployment:** GCP Cloud Build (optional), Vercel CLI/Git Integration
*   **Infrastructure Management:** Manual Setup / GCP Console / Terraform (optional)
*   **Monitoring:** GCP Cloud Monitoring & Logging, Vercel Analytics

## Project Structure

```plaintext
movielens-recommender-gcp/
├── .gitignore
├── README.md                 # This file
│
├── backend/                  # FastAPI application (Cloud Run service)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── app/                  # Core backend application code
│   │   ├── api/              # API endpoints (routers)
│   │   ├── core/             # Config, security
│   │   ├── data_access/      # DB/Cache interaction logic
│   │   ├── models/           # Pydantic models
│   │   ├── services/         # Business logic (recommendations, etc.)
│   │   └── utils/
│   └── tests/                # Backend tests
│
├── frontend/                 # Next.js application (Vercel deployment)
│   ├── src/                  # Frontend source code
│   ├── public/
│   ├── package.json
│   ├── next.config.js
│   └── ...                   # Standard Next.js files
│
├── data_processing/          # Scripts for offline tasks (Cloud Functions/Workflows)
│   ├── requirements.txt
│   ├── common/               # Shared utilities for data processing
│   ├── scripts/              # Individual processing scripts (download, embeddings, etc.)
│   └── cloud_function/       # Example packaging for Cloud Function deployment
│
├── infra/                    # Optional: Infrastructure as Code (Terraform)
│
└── cloudbuild.yaml           # Optional: Cloud Build config for CI/CD

Setup & Installation
Prerequisites

    Python 3.9+ and Pip

    Node.js (LTS version recommended) and npm/yarn

    Docker Desktop

    Google Cloud SDK (gcloud) installed and authenticated

    Vercel CLI (optional, for manual frontend deployment)

    Access to:

        GCP Project with Billing Enabled (required for some APIs, even within free tier limits)

        MongoDB Atlas Account (create an M0 cluster)

        Supabase Account (create a free project)

        Redis Provider Account (e.g., Upstash - create a free database)

Steps

    Clone Repository:

    git clone <your-repository-url>
    cd movielens-recommender-gcp

    Set Up Cloud Resources:

    Create a GCP Project.

    Enable necessary APIs (Cloud Run, Cloud Build, Artifact Registry, Cloud Functions, Cloud Storage, Secret Manager, Cloud Scheduler).

    Create a GCS Bucket. Note the name.

    Create a MongoDB Atlas M0 cluster. Get the connection string (ensure your IP is whitelisted or use 0.0.0.0/0 for initial testing - not recommended for production).

    Create a Supabase project. Note the Project URL, anon key, and JWT Secret (under API settings).

    Create a free Redis instance (e.g., Upstash). Get the connection URL.

    (Recommended) Store secrets (MongoDB URI, Redis URL, Supabase JWT Secret, Supabase Service Role Key) in GCP Secret Manager. Grant your Cloud Run service account and Cloud Function service account access to these secrets.

Configure Environment Variables:

    Backend: Copy backend/.env.sample to backend/.env and fill in the values for local development (MONGODB_URI, REDIS_URL, SUPABASE_URL, SUPABASE_JWT_SECRET, GCS_BUCKET_NAME, etc.). Do not commit .env!

    Frontend: Copy frontend/.env.sample to frontend/.env.local and fill in the values (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL - this will be your local backend URL initially, later your Cloud Run URL). Do not commit .env.local!

    Data Processing: Ensure the necessary environment variables (GCS_BUCKET_NAME, MONGODB_URI, HF_MODEL_NAME) are available when running these scripts (e.g., set them in your shell or configure them in Cloud Function environment variables).

Install Dependencies:

    Backend:
        cd backend
        python -m venv venv
        source venv/bin/activate # or venv\Scripts\activate on Windows
        pip install -r requirements.txt
        cd ..
    Frontend:
        cd frontend
        npm install # or yarn install
        cd ..
    Data Processing:
        cd data_processing
        python -m venv venv
        source venv/bin/activate # or venv\Scripts\activate on Windows
        pip install -r requirements.txt
        cd ..

Run Initial Data Pipeline:

    Activate the data_processing virtual environment.

    Ensure necessary environment variables are set.

    Run the scripts in data_processing/scripts/ in order:

          
    # Ensure data_processing venv is active
    # Ensure MONGODB_URI, GCS_BUCKET_NAME etc. are set in your environment
    python data_processing/scripts/01_download_movielens.py
    python data_processing/scripts/02_generate_embeddings.py
    python data_processing/scripts/03_load_interactions.py

Note: Embedding generation can take time and consume memory. This step must be run outside the Cloud Run service.

Running Locally

    Start Backend API:

        Activate the backend virtual environment.

        Ensure backend/.env is configured.

        Run the FastAPI server (from the backend/ directory):
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
        The API will be available at http://localhost:8000.

    Start Frontend:

    Ensure frontend/.env.local is configured (point NEXT_PUBLIC_API_URL to http://localhost:8000).

    Run the Next.js development server (from the frontend/ directory):
    npm run dev # or yarn dev

        The frontend will be available at http://localhost:3000.

Deployment

    Backend (GCP Cloud Run):

        Build the Docker image: docker build -t gcr.io/YOUR_GCP_PROJECT_ID/movielens-rec-api:latest ./backend

        Push the image to Google Container Registry (GCR) or Artifact Registry: docker push gcr.io/YOUR_GCP_PROJECT_ID/movielens-rec-api:latest

        Deploy to Cloud Run using gcloud or the GCP Console:

            Select the pushed image.

            Choose a region (e.g., us-central1).

            Crucially set Minimum Instances to 0.

            Set Maximum Instances to a low number (e.g., 2) initially.

            Configure CPU/Memory (e.g., 1 CPU, 512MiB).

            Set environment variables by linking to Secret Manager secrets (MONGODB_URI, REDIS_URL, SUPABASE_JWT_SECRET, etc.).

            Configure the service account (ensure it has permissions for Secret Manager, GCS, etc.).

            Allow unauthenticated invocations (if the frontend needs to call it directly) or configure authentication.

        Note the deployed service URL and update NEXT_PUBLIC_API_URL in the frontend environment variables (Vercel).

        (Optional) Set up Cloud Build for automated builds and deployments from Git.

    Frontend (Vercel):

        Connect your Git repository (GitHub, GitLab, Bitbucket) to Vercel.

        Configure the project settings (framework preset: Next.js, root directory: frontend).

        Add environment variables in the Vercel project settings: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL (pointing to your deployed Cloud Run service URL).

        Deploy! Vercel will automatically build and deploy on pushes to the main branch.

    Data Processing (GCP Cloud Functions):

        Package the relevant script(s) from data_processing/ for Cloud Function deployment (see data_processing/cloud_function/ example).

        Deploy using gcloud functions deploy or the GCP Console.

        Choose Gen 2 for potentially longer timeouts and more memory if needed for embedding generation.

        Set required environment variables (linking to Secret Manager recommended).

        Configure triggers (e.g., HTTP for manual runs, Cloud Scheduler for periodic tasks, Pub/Sub).

        Assign an appropriate service account with permissions (GCS, MongoDB access via VPC connector if needed, Secret Manager).

    Infrastructure:

        Ensure your MongoDB Atlas, Supabase, Redis, and GCS resources are provisioned and configured correctly (networking, security rules, etc.).

API Endpoints

Key backend API endpoints include:

    GET /health: Service health check.

    GET /api/movies: List movies (paginated, filterable).

    GET /api/movies/{movie_id}: Get details for a specific movie.

    POST /api/interactions: Record a user interaction (requires auth).

    GET /api/recommendations/user/me: Get personalized recommendations for the authenticated user (requires auth).

    GET /api/recommendations/item/{movie_id}: Get movies similar to a given movie.

(See API documentation or code for full details)
Free Tier Optimization Strategies

This project heavily relies on:

    Cloud Run minInstances: 0: Scaling to zero when idle is essential.

    Asynchronous Heavy Lifting: Using Cloud Functions/Workflows for data processing, embedding generation, and updates outside the API request cycle.

    GCS for Caching: Storing the downloaded MovieLens dataset to avoid repeated downloads.

    MongoDB Atlas M0: Leveraging the free tier for data storage.

    Supabase Free Tier: For authentication.

    External Redis Free Tier: For caching API responses and computations.

    Efficient Data Loading: Fetching only necessary data/embeddings from MongoDB per request.

    Lightweight HF Model: Using smaller Sentence Transformer models.

    Monitoring Usage: Keeping a close eye on GCP billing and Cloud Monitoring dashboards.

Monitoring

    GCP: Use Cloud Monitoring and Cloud Logging to track Cloud Run instance time, request latency/errors, CPU/Memory usage, and Cloud Function executions/errors. Set up alerts for billing thresholds and error rates.

    Vercel: Use Vercel Analytics for frontend traffic and performance monitoring.

    External Services: Monitor usage dashboards for MongoDB Atlas, Supabase, and your Redis provider. Check Redis cache hit ratio.

Contributing

(Optional: Add guidelines if you expect contributions)
License

(Choose and specify your license, e.g., MIT)

MIT


Remember to:

1.  Replace placeholders like `<your-repository-url>`, `YOUR_GCP_PROJECT_ID`.
2.  Create `.env.sample` files in `backend/` and `frontend/` based on the required variables.
3.  Consider adding an `ARCHITECTURE.md` file with a diagram.
4.  Choose and add a `LICENSE` file.
5.  Fill in any optional sections (like Badges, Contributing) if desired.