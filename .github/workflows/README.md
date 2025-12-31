# GitHub Actions Setup Guide

## No Secrets Required! 🎉

This workflow runs without needing any server credentials. Files are saved as GitHub Actions artifacts that you can download.

## How to Run

1. Go to your repository → **Actions** tab
2. Select **"YouTube Pipeline"** from the workflow list
3. Click **"Run workflow"** button
4. Enter your YouTube search query (e.g., "Bohemian Rhapsody Queen")
5. Click **"Run workflow"**

The workflow will:
- Build the Docker container
- Download and process the audio
- Separate audio into stems (drums, vocals, guitar, synth)
- Save output files as downloadable artifacts (90 days retention)

## Downloading Artifacts to Your Local Drive

### Option 1: Manual Download
1. After workflow completes, go to the **Actions** tab
2. Click on the completed workflow run
3. Scroll down to **Artifacts** section
4. Click **separated-stems-XXX** to download
5. Extract the ZIP file to `F:\Split YT Links Project`

### Option 2: Automated Download Script
Use the included script to automatically download the latest artifacts:

1. **Create a GitHub Personal Access Token:**
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scope: `repo` (for private repos) or `public_repo` (for public repos)
   - Copy the token

2. **Run the download script:**
   ```bash
   cd youtube_pipeline
   python download_artifacts.py --latest --output "F:\Split YT Links Project"
   ```
   Or set the token as environment variable:
   ```bash
   set GITHUB_TOKEN=your_token_here
   python download_artifacts.py --latest
   ```

3. **Or use the batch file:**
   ```bash
   download_artifacts.bat YOUR_GITHUB_TOKEN
   ```

### Script Options:
- `--list` - List all available artifacts
- `--latest` - Download the most recent artifact
- `--artifact-id ID` - Download a specific artifact by ID
- `--output PATH` - Specify output directory (default: `F:\Split YT Links Project`)

## Free Tier Limits

- **Public repos**: Unlimited minutes
- **Private repos**: 2,000 minutes/month
- **Job timeout**: 6 hours maximum (configured in workflow)

