# Using Your Computer as a Proxy for YouTube Downloads

This guide shows you how to use your computer as a proxy so Render routes YouTube requests through your residential IP address, bypassing YouTube's bot detection.

## Quick Start

1. **Run the proxy server on your computer:**
   ```bash
   python local_proxy.py
   ```
   This starts a proxy server on `http://127.0.0.1:8888`

2. **Expose it publicly using ngrok (recommended):**
   ```bash
   ngrok http 8888
   ```
   This will give you a public URL like `https://abc123.ngrok.io`

3. **Set the proxy URL on Render:**
   - Go to your Render dashboard
   - Select your service
   - Go to "Environment" tab
   - Add environment variable:
     - Key: `YOUTUBE_PROXY_URL`
     - Value: `http://abc123.ngrok.io` (use your ngrok URL)

4. **Redeploy your service** (or it will pick up the env var automatically)

## Alternative Tunneling Services

### Option 1: ngrok (Recommended)
```bash
# Install ngrok from https://ngrok.com/download
ngrok http 8888
```
- Free tier available
- Easy to use
- URL changes on restart (free tier)

### Option 2: cloudflared (Cloudflare Tunnel)
```bash
# Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
cloudflared tunnel --url http://localhost:8888
```
- Free
- More stable URLs
- Requires Cloudflare account

### Option 3: localtunnel
```bash
npm install -g localtunnel
lt --port 8888
```
- Free
- Simple
- URLs can be unstable

## How It Works

1. Your computer runs a proxy server locally
2. A tunneling service (ngrok/cloudflared) exposes it publicly
3. Render's yt-dlp uses your proxy for all YouTube requests
4. YouTube sees your residential IP instead of Render's datacenter IP
5. Downloads work! 🎉

## Security Notes

- The proxy server accepts connections from anywhere (via the tunnel)
- Consider adding authentication if you're concerned about security
- The proxy only forwards requests, it doesn't store data
- Your IP will be visible to YouTube (this is intentional)

## Troubleshooting

**Proxy not working?**
- Make sure the proxy server is running
- Check that ngrok/cloudflared is running and shows your proxy URL
- Verify the `YOUTUBE_PROXY_URL` env var is set correctly on Render
- Check Render logs for proxy connection errors

**ngrok URL keeps changing?**
- Use ngrok's authtoken for stable URLs: `ngrok config add-authtoken YOUR_TOKEN`
- Or use cloudflared for more stable URLs

**Connection refused?**
- Make sure the proxy server is running on port 8888
- Check firewall settings
- Try a different port: `python local_proxy.py 9999`

## Advanced: Adding Authentication

If you want to secure your proxy, you can modify `local_proxy.py` to require authentication. However, for yt-dlp to use it, you'll need to include credentials in the URL:

```
YOUTUBE_PROXY_URL=http://username:password@your-proxy-url.com
```

