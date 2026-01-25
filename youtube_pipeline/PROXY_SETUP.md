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

## Security Risks & Mitigations

### ⚠️ Potential Risks

1. **Anyone with the ngrok URL can use your proxy**
   - If someone discovers your ngrok URL, they could use your IP for requests
   - This could be used for malicious activities (though unlikely)
   - Your IP could be logged by websites you proxy to

2. **Your residential IP is exposed**
   - YouTube will see your home IP address
   - Your ISP might notice unusual traffic patterns
   - Could potentially be associated with your identity

3. **Legal/Terms of Service concerns**
   - Using a proxy to bypass YouTube's restrictions may violate YouTube's ToS
   - Downloading copyrighted content has legal implications depending on jurisdiction
   - The proxy itself isn't illegal, but usage might be

4. **Network security**
   - If your computer is compromised, the proxy could be abused
   - Need to keep your computer running continuously

### ✅ Security Mitigations

**Use the secure version:**
```bash
# Set strong password
export PROXY_USERNAME=your_username
export PROXY_PASSWORD=your_strong_password
python local_proxy_secure.py
```

**On Render, use authenticated URL:**
```
YOUTUBE_PROXY_URL=http://your_username:your_password@your-ngrok-url
```

**Additional safety measures:**
1. **Use ngrok IP whitelist** (if available on your plan)
2. **Only run when needed** - don't leave it running 24/7
3. **Monitor logs** - check what's being proxied
4. **Use strong password** - don't use default credentials
5. **Consider VPN** - route proxy through VPN for extra anonymity
6. **Check your ISP's ToS** - some ISPs prohibit running servers

### 🛡️ Safer Alternatives

If you're concerned about risks:
1. **Use a VPS** - Rent a cheap VPS with residential IP instead
2. **Use a proxy service** - Pay for a residential proxy service (Bright Data, etc.)
3. **Use VPN + proxy** - Route through VPN first for extra protection
4. **Manual download** - Download locally, upload to Render (no proxy needed)

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

