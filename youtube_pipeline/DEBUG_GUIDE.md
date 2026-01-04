# Debugging Guide - What Logs to Provide

When reporting issues, please provide the following information:

## 1. Server Terminal Logs

**Where:** The terminal/console where you ran `python api_server.py`

**What to look for:**
- Any ERROR messages
- Cookie file detection messages
- YouTube search results
- Download attempts and failures
- Client retry attempts (ios, android, web, etc.)

**Example of useful log lines:**
```
INFO - Using cookie file: ../cookies.txt (age: X days)
INFO - Found video: [Title] - [URL]
ERROR - Error downloading audio: [error message]
INFO - Retrying with client(s): ['web']
```

## 2. Browser Console Logs

**How to access:**
- Press F12 (or right-click → Inspect)
- Go to "Console" tab
- Look for red error messages

**What to capture:**
- Any JavaScript errors
- Failed API requests (check Network tab too)
- Error messages from the web interface

## 3. Network Tab (Browser)

**How to access:**
- Press F12 → "Network" tab
- Try processing a song
- Look for failed requests (red entries)
- Click on failed requests to see error details

**What to check:**
- `/process` endpoint - what response code? (200, 400, 500?)
- `/static/style.css` and `/static/script.js` - are they loading? (200 OK?)
- Response body of failed requests

## 4. Specific Information to Provide

When reporting an issue, include:

1. **The YouTube URL or search query you used**
2. **The exact error message** (copy/paste from logs)
3. **Which step failed:**
   - Search? (can't find video)
   - Download? (age restriction, network error, etc.)
   - Separation? (Demucs error)
   - Upload? (server connection error)
4. **Cookie file status:**
   - Is it detected? (check server logs)
   - How old is it? (check server logs)
5. **Browser console errors** (if any)
6. **Full server log output** from when you tried to process

## 5. Quick Test Commands

Run these to check your setup:

```bash
# Check if cookie file is detected
cd youtube_pipeline
python -c "from pipeline import YouTubePipeline; p = YouTubePipeline(); print('Cookie:', p.cookie_file)"

# Test YouTube search
python -c "from pipeline import YouTubePipeline; p = YouTubePipeline(); print(p.search_youtube('test song'))"
```

## Common Issues and What to Check

### "Age restriction" errors
- Check cookie file age (should be < 7 days)
- Check server logs for cookie file detection
- Try exporting fresh cookies

### "No such file or directory"
- Check config.json exists
- Check cookie file path is correct
- Check output directory exists

### "Module not found"
- Run: `python check_dependencies.py`
- Install missing modules: `pip install --user [module]`

### Static files not loading
- Check browser console for 404 errors
- Verify files exist: `ls static/*.css static/*.js`
- Check server logs for static file requests

