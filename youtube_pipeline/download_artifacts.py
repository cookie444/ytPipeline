#!/usr/bin/env python3
"""
Download artifacts from GitHub Actions and save to local drive.
"""

import os
import sys
import zipfile
import requests
from pathlib import Path
import argparse

# Default output directory
DEFAULT_OUTPUT_DIR = Path("F:/Split YT Links Project")

def download_artifact(owner: str, repo: str, artifact_id: int, token: str, output_dir: Path):
    """Download a GitHub Actions artifact."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get artifact download URL
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip"
    
    print(f"Downloading artifact {artifact_id}...")
    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()
    
    # Save to temporary zip
    zip_path = output_dir / f"artifact_{artifact_id}.zip"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"Downloaded to: {zip_path}")
    
    # Extract zip
    extract_dir = output_dir / f"extracted_{artifact_id}"
    extract_dir.mkdir(exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    print(f"Extracted to: {extract_dir}")
    
    # Clean up zip file
    zip_path.unlink()
    
    return extract_dir

def list_artifacts(owner: str, repo: str, token: str, workflow_name: str = None):
    """List available artifacts."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts"
    params = {"per_page": 100}
    
    if workflow_name:
        # Get workflow runs first
        workflow_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows"
        workflow_response = requests.get(workflow_url, headers=headers)
        workflow_response.raise_for_status()
        
        workflows = workflow_response.json().get("workflows", [])
        workflow_id = None
        for wf in workflows:
            if workflow_name.lower() in wf.get("name", "").lower():
                workflow_id = wf["id"]
                break
        
        if workflow_id:
            runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
            runs_response = requests.get(runs_url, headers=headers, params={"per_page": 10})
            runs_response.raise_for_status()
            runs = runs_response.json().get("workflow_runs", [])
            if runs:
                run_id = runs[0]["id"]
                url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    artifacts = response.json().get("artifacts", [])
    return artifacts

def main():
    parser = argparse.ArgumentParser(description="Download GitHub Actions artifacts")
    parser.add_argument("--owner", default="cookie444", help="GitHub owner/username")
    parser.add_argument("--repo", default="ytPipeline", help="Repository name")
    parser.add_argument("--token", help="GitHub personal access token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--list", action="store_true", help="List available artifacts")
    parser.add_argument("--artifact-id", type=int, help="Specific artifact ID to download")
    parser.add_argument("--latest", action="store_true", help="Download latest artifact")
    parser.add_argument("--workflow", default="YouTube Pipeline", help="Workflow name filter")
    
    args = parser.parse_args()
    
    # Get token from env or arg
    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub token required. Set GITHUB_TOKEN env var or use --token")
        print("Create a token at: https://github.com/settings/tokens")
        print("Required scope: repo (for private repos) or public_repo (for public repos)")
        sys.exit(1)
    
    if args.list:
        print("Fetching artifacts...")
        artifacts = list_artifacts(args.owner, args.repo, token, args.workflow)
        
        if not artifacts:
            print("No artifacts found.")
            return
        
        print(f"\nFound {len(artifacts)} artifact(s):\n")
        for art in artifacts:
            print(f"ID: {art['id']}")
            print(f"Name: {art['name']}")
            print(f"Size: {art['size_in_bytes'] / 1024 / 1024:.2f} MB")
            print(f"Created: {art['created_at']}")
            print(f"Expires: {art['expires_at']}")
            print("-" * 50)
    
    elif args.artifact_id:
        download_artifact(args.owner, args.repo, args.artifact_id, token, args.output)
    
    elif args.latest:
        print("Fetching latest artifact...")
        artifacts = list_artifacts(args.owner, args.repo, token, args.workflow)
        
        if not artifacts:
            print("No artifacts found.")
            return
        
        latest = artifacts[0]  # API returns most recent first
        print(f"Downloading latest artifact: {latest['name']} (ID: {latest['id']})")
        download_artifact(args.owner, args.repo, latest['id'], token, args.output)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

