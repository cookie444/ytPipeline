# GitHub Actions Setup Guide

## Required GitHub Secrets

To use this workflow, you need to add the following secrets to your GitHub repository:

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add:

### Required Secrets:
- **`SERVER_HOST`** - Your server hostname or IP address (e.g., `example.com` or `192.168.1.100`)
- **`SERVER_USERNAME`** - SSH username for your server
- **`SERVER_PASSWORD`** - SSH password (or use SSH key method below)

### Optional Secrets:
- **`SERVER_PORT`** - SSH port (defaults to 22 if not set)
- **`SERVER_REMOTE_PATH`** - Remote directory path (defaults to `/tmp/` if not set)

## Alternative: SSH Key Authentication

If you prefer SSH key authentication instead of password:

1. Add secret **`SERVER_SSH_KEY`** - Your private SSH key content
2. Modify the workflow to use the key (see workflow file comments)

## How to Run

1. Go to your repository → **Actions** tab
2. Select **"YouTube Pipeline"** from the workflow list
3. Click **"Run workflow"** button
4. Enter your YouTube search query (e.g., "Bohemian Rhapsody Queen")
5. Click **"Run workflow"**

The workflow will:
- Build the Docker container
- Download and process the audio
- Upload results to your server
- Save output files as downloadable artifacts (7 days retention)

## Free Tier Limits

- **Public repos**: Unlimited minutes
- **Private repos**: 2,000 minutes/month
- **Job timeout**: 6 hours maximum (configured in workflow)

