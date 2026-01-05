# Deploying to Render

This guide will help you deploy the YouTube Audio Processing Pipeline to Render as a transient web service.

## Prerequisites

1. A [Render](https://render.com) account (free tier available)
2. Your code pushed to a Git repository (GitHub, GitLab, or Bitbucket)
3. A password for protecting the web interface

## Deployment Steps

### Option 1: Using Render Dashboard (Recommended)

1. **Log in to Render Dashboard**
   - Go to https://dashboard.render.com
   - Sign up or log in

2. **Create a New Web Service**
   - Click "New +" → "Web Service"
   - Connect your Git repository
   - Select the repository containing this project

3. **Configure the Service**
   - **Name**: `youtube-pipeline` (or your preferred name)
   - **Region**: Choose closest to you (e.g., Oregon, Frankfurt)
   - **Branch**: `main` (or your default branch)
   - **Root Directory**: `youtube_pipeline` (if your code is in a subdirectory)
   - **Runtime**: `Docker`
   - **Build Command**: Leave empty (Docker handles this)
   - **Start Command**: `python api_server.py`
   - **Plan**: Free (or upgrade for better performance)

4. **Set Environment Variables**
   Click "Environment" and add:
   - `APP_PASSWORD`: Your desired password (e.g., `mySecurePassword123`)
   - `PORT`: `5000` (Render sets this automatically, but good to have)
   - `HOST`: `0.0.0.0`
   - `CONFIG_PATH`: `config.json`
   - `SECRET_KEY`: Generate a random string (or leave Render to auto-generate)
   - `PYTHONUNBUFFERED`: `1`
   - `PYTHONIOENCODING`: `utf-8`
   - `TORCHAUDIO_USE_SOUNDFILE`: `1`

   **Optional** (for server upload functionality):
   - Add server configuration to `config.json` or via environment variables

5. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy your service
   - Wait for deployment to complete (5-10 minutes on free tier)

6. **Access Your Service**
   - Once deployed, you'll get a URL like: `https://youtube-pipeline.onrender.com`
   - Visit the URL and log in with your `APP_PASSWORD`

### Option 2: Using Render Blueprint (render.yaml)

1. **Push render.yaml to your repository**
   - The `render.yaml` file is already in the project

2. **Deploy via Blueprint**
   - In Render dashboard, click "New +" → "Blueprint"
   - Connect your repository
   - Render will detect `render.yaml` and create the service

3. **Set Environment Variables**
   - Go to the created service
   - Add `APP_PASSWORD` as a secret environment variable
   - Other variables are defined in `render.yaml`

## Important Notes

### Free Tier Limitations

- **Spins down after 15 minutes of inactivity**
- **Limited CPU/RAM** (may be slow for audio processing)
- **Build time limits** (may need to optimize Dockerfile)
- **Cold starts** (first request after spin-down takes ~30 seconds)

### Transient System Behavior

- The system is designed to be transient - files are processed and cleaned up
- Output files are saved to `/app/output` (ephemeral storage)
- For persistent storage, configure server upload in `config.json`

### Security

- **Always set a strong `APP_PASSWORD`** via environment variables
- Never commit passwords to Git
- Use Render's secret environment variables for sensitive data

### Performance Tips

1. **Upgrade Plan**: Consider Render's paid plans for better performance
2. **Optimize Dockerfile**: Multi-stage builds can reduce image size
3. **Caching**: Render caches Docker layers between deployments
4. **Queue System**: The built-in queue prevents resource exhaustion

## Troubleshooting

### Build Fails

- Check Dockerfile syntax
- Ensure all dependencies are in `requirements.txt`
- Check Render build logs for specific errors

### Service Won't Start

- Verify `PORT` environment variable is set
- Check that `api_server.py` is the entry point
- Review application logs in Render dashboard

### Authentication Issues

- Ensure `APP_PASSWORD` is set correctly
- Check that `SECRET_KEY` is set (or auto-generated)
- Clear browser cookies and try again

### Audio Processing Fails

- Free tier may have limited resources
- Check logs for specific error messages
- Ensure FFmpeg is installed (included in Dockerfile)
- Verify Demucs dependencies are correct

## Monitoring

- **Logs**: Available in Render dashboard under "Logs"
- **Metrics**: Basic metrics available on free tier
- **Health Check**: `/health` endpoint for monitoring

## Updating the Service

- **Auto-deploy**: Enabled by default on git push
- **Manual deploy**: Click "Manual Deploy" in dashboard
- **Rollback**: Available in deployment history

## Support

- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
- Project Issues: Check your repository's issue tracker

