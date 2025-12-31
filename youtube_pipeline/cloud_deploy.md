# Cloud Deployment Guide

This guide provides step-by-step instructions for deploying the YouTube Audio Processing Pipeline to various cloud platforms.

## Quick Start

The pipeline is designed to run as a transient job (one-time execution) rather than a long-running service. This makes it ideal for:
- AWS ECS Tasks
- Google Cloud Run Jobs
- Azure Container Instances
- Kubernetes Jobs
- Scheduled Lambda functions (with container support)

## AWS Deployment

### Option 1: ECS Fargate Task

1. **Build and push to ECR:**
```bash
# Create ECR repository
aws ecr create-repository --repository-name youtube-pipeline

# Get login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and tag
docker build -t youtube-pipeline .
docker tag youtube-pipeline:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/youtube-pipeline:latest

# Push
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/youtube-pipeline:latest
```

2. **Create Task Definition:**
```json
{
  "family": "youtube-pipeline",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "pipeline",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/youtube-pipeline:latest",
      "essential": true,
      "command": ["python", "pipeline.py", "artist - song title"],
      "environment": [],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/youtube-pipeline",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

3. **Run Task:**
```bash
aws ecs run-task \
  --cluster your-cluster \
  --task-definition youtube-pipeline \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],assignPublicIp=ENABLED}"
```

### Option 2: Lambda with Container Image

1. Build and push to ECR (same as above)

2. Create Lambda function using the container image

3. Configure:
   - Memory: 4096 MB (max)
   - Timeout: 15 minutes (max)
   - Environment variables for config

## Google Cloud Deployment

### Cloud Run Jobs

```bash
# Build and push
gcloud builds submit --tag gcr.io/<project-id>/youtube-pipeline

# Create Cloud Run Job
gcloud run jobs create youtube-pipeline \
  --image gcr.io/<project-id>/youtube-pipeline \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-retries 0 \
  --command python \
  --args pipeline.py,"artist - song title"

# Execute job
gcloud run jobs execute youtube-pipeline --region us-central1
```

### Cloud Functions (Gen 2)

For API-based triggering, use the `api_server.py`:

```bash
gcloud functions deploy youtube-pipeline-api \
  --gen2 \
  --runtime python311 \
  --source . \
  --entry-point app \
  --memory 4Gi \
  --timeout 540s \
  --region us-central1 \
  --allow-unauthenticated
```

## Azure Deployment

### Container Instances

```bash
# Build and push to ACR
az acr build --registry <registry-name> --image youtube-pipeline:latest .

# Create container instance
az container create \
  --resource-group <resource-group> \
  --name youtube-pipeline \
  --image <registry-name>.azurecr.io/youtube-pipeline:latest \
  --cpu 2 \
  --memory 4 \
  --registry-login-server <registry-name>.azurecr.io \
  --registry-username <username> \
  --registry-password <password> \
  --command-line "python pipeline.py 'artist - song title'"
```

## Kubernetes Deployment

### Job Manifest

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: youtube-pipeline
spec:
  template:
    spec:
      containers:
      - name: pipeline
        image: youtube-pipeline:latest
        command: ["python", "pipeline.py"]
        args: ["artist - song title"]
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "4Gi"
            cpu: "2"
        volumeMounts:
        - name: config
          mountPath: /app/config.json
          subPath: config.json
          readOnly: true
      volumes:
      - name: config
        secret:
          secretName: pipeline-config
      restartPolicy: Never
  backoffLimit: 0
```

### Create Secret from Config

```bash
kubectl create secret generic pipeline-config \
  --from-file=config.json=./config.json
```

## Environment Variables

Instead of mounting config files, you can use environment variables:

```python
# In pipeline.py, add support for env vars
import os

config = {
    "server": {
        "host": os.getenv("SERVER_HOST"),
        "username": os.getenv("SERVER_USERNAME"),
        "password": os.getenv("SERVER_PASSWORD"),
        # ...
    }
}
```

## Cost Optimization

- Use spot/preemptible instances when possible
- Set appropriate resource limits
- Clean up temporary files (already implemented)
- Use object storage (S3/GCS) instead of direct server upload for large files

## Monitoring

Add logging to cloud watch/logging services:

```python
import logging
import sys

# CloudWatch handler (AWS)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
```

## Security Best Practices

1. **Use Secrets Management:**
   - AWS: Secrets Manager or Parameter Store
   - GCP: Secret Manager
   - Azure: Key Vault

2. **SSH Keys:**
   - Store private keys in secrets
   - Use IAM roles when possible
   - Rotate credentials regularly

3. **Network Security:**
   - Use VPC/private networks
   - Restrict outbound access
   - Use VPN for server connections

## Troubleshooting

### Out of Memory
- Increase container memory limits
- Process shorter audio segments
- Use GPU instances if available

### Timeout Issues
- Increase timeout limits
- Optimize Demucs parameters
- Use faster models (mdx_extra instead of htdemucs)

### Network Issues
- Check firewall rules
- Verify DNS resolution
- Test connectivity from container


