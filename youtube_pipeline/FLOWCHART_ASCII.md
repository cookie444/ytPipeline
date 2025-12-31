# YouTube Pipeline - Box Flowchart

## Local Option

```
+------------------+
|      START       |
+------------------+
         |
         |
+------------------+
|  Setup config.json|
+------------------+
         |
         |
+------------------+
| Install deps     |
| (pip install)    |
+------------------+
         |
         |
+------------------+
| Run: python      |
| pipeline.py      |
| "query"          |
+------------------+
         |
         |
+------------------+
|  Search YouTube  |
+------------------+
         |
         |
+------------------+
| Download Audio   |
| (Best Quality)   |
| Convert to WAV   |
+------------------+
         |
         |
+------------------+
| Separate Audio   |
| (Demucs AI)      |
| - drums.wav      |
| - vocals.wav     |
| - guitar.wav     |
| - synth.wav      |
+------------------+
         |
         |
+------------------+
|   Create ZIP     |
|   Archive        |
+------------------+
         |
         |
+------------------+
| Upload to Server |
| (SCP)            |
+------------------+
         |
         |
+------------------+
|    Cleanup       |
|  Temp Files     |
+------------------+
         |
         |
+------------------+
|      DONE        |
| Files on Server  |
+------------------+
```

## Cloud Option

```
+------------------+
|      START       |
+------------------+
         |
         |
+------------------+
| Build Docker     |
| Image            |
+------------------+
         |
         |
+------------------+
| Push to Registry |
| (ECR/GCR/ACR)    |
+------------------+
         |
         |
+------------------+
| Deploy to Cloud  |
| Platform         |
+------------------+
         |
         |
+------------------+
| Choose Platform: |
| - AWS ECS Task   |
| - GCP Run Job    |
| - Azure ACI      |
| - Kubernetes Job |
+------------------+
         |
         |
+------------------+
| Trigger Job      |
| (API/CLI/        |
|  Scheduler)      |
+------------------+
         |
         |
+------------------+
| Container Starts |
| Load Config      |
+------------------+
         |
         |
+------------------+
|  Search YouTube  |
+------------------+
         |
         |
+------------------+
| Download Audio   |
| (Best Quality)   |
| Convert to WAV   |
+------------------+
         |
         |
+------------------+
| Separate Audio   |
| (Demucs AI)      |
| - drums.wav      |
| - vocals.wav     |
| - guitar.wav     |
| - synth.wav      |
+------------------+
         |
         |
+------------------+
|   Create ZIP     |
|   Archive        |
+------------------+
         |
         |
+------------------+
| Upload to Server |
| (SCP)            |
+------------------+
         |
         |
+------------------+
|    Cleanup       |
|  Temp Files      |
+------------------+
         |
         |
+------------------+
| Container Stops  |
+------------------+
         |
         |
+------------------+
|      DONE        |
| Files on Server  |
+------------------+
```

## Combined Flow (Local vs Cloud)

```
+------------------+              +------------------+
|   LOCAL OPTION   |              |  CLOUD OPTION    |
+------------------+              +------------------+
         |                                 |
         |                                 |
+------------------+              +------------------+
|  Setup config.json|              | Build Docker     |
+------------------+              +------------------+
         |                                 |
         |                                 |
+------------------+              +------------------+
| Install deps     |              | Push to Registry |
+------------------+              +------------------+
         |                                 |
         |                                 |
+------------------+              +------------------+
| Run: python      |              | Deploy Cloud     |
| pipeline.py      |              +------------------+
+------------------+                       |
         |                                 |
         |                                 |
         +-------------+------------------+
                       |
                       |
              +------------------+
              | COMMON PIPELINE |
              +------------------+
                       |
                       |
              +------------------+
              |  Search YouTube  |
              +------------------+
                       |
                       |
              +------------------+
              | Download Audio   |
              | (Best Quality)   |
              | Convert to WAV   |
              +------------------+
                       |
                       |
              +------------------+
              | Separate Audio   |
              | (Demucs AI)      |
              | - drums.wav      |
              | - vocals.wav     |
              | - guitar.wav     |
              | - synth.wav      |
              +------------------+
                       |
                       |
              +------------------+
              |   Create ZIP     |
              |   Archive        |
              +------------------+
                       |
                       |
              +------------------+
              | Upload to Server |
              | (SCP)            |
              +------------------+
                       |
                       |
              +------------------+
              |    Cleanup       |
              |  Temp Files      |
              +------------------+
                       |
                       |
              +------------------+
              |      DONE        |
              | Files on Server  |
              +------------------+
```

## Detailed Pipeline Steps

```
+------------------+
|  INPUT: Query    |
|  String          |
+------------------+
         |
         |
+------------------+
|   [SEARCH]       |
|  yt-dlp search   |
|  Find video URL  |
+------------------+
         |
         |
+------------------+
|  [DOWNLOAD]      |
|  yt-dlp download |
|  Get best audio  |
|  Convert to WAV  |
|  Save to temp    |
+------------------+
         |
         |
+------------------+
|  [SEPARATE]      |
|  Run Demucs      |
|  Extract:        |
|  - drums.wav     |
|  - vocals.wav    |
|  - guitar.wav    |
|  - synth.wav     |
+------------------+
         |
         |
+------------------+
|  [PACKAGE]       |
|  Create ZIP      |
|  Add all stems   |
|  Compress        |
+------------------+
         |
         |
+------------------+
|  [UPLOAD]        |
|  Connect via SCP |
|  Transfer ZIP    |
|  Verify upload   |
+------------------+
         |
         |
+------------------+
|  [CLEANUP]       |
|  Remove temp     |
|  files           |
|  Free disk space |
+------------------+
         |
         |
+------------------+
|      DONE        |
|  Files on Server |
+------------------+
```

## Error Handling Flow

```
+------------------+
|   Each Step      |
+------------------+
         |
         |
+------------------+
|      TRY         |
+------------------+
         |
    +----+----+
    |         |
    |         |
+-------+ +-------+
|SUCCESS| | ERROR |
+-------+ +-------+
    |         |
    |         |
    |    +------------------+
    |    | Log Error        |
    |    | Print Stack      |
    |    +------------------+
    |         |
    |         |
    |    +------------------+
    |    | Cleanup Temp    |
    |    | Files           |
    |    +------------------+
    |         |
    |         |
    |    +------------------+
    |    | Return False    |
    |    | Exit Code 1     |
    |    +------------------+
    |
+------------------+
| Continue to      |
| Next Step        |
+------------------+
```

## API Server Flow

```
+------------------+
|  Start API       |
|  Server (Flask)  |
+------------------+
         |
         |
+------------------+
|  Listen on       |
|  Port 5000       |
+------------------+
         |
         |
+------------------+
|  POST /process   |
|  {query: "..."}  |
+------------------+
         |
         |
+------------------+
|  Initialize     |
|  Pipeline        |
+------------------+
         |
         |
+------------------+
|  Run Pipeline    |
|  (Same steps     |
|   as above)     |
+------------------+
         |
         |
+------------------+
|  Return JSON     |
|  Response        |
|  {success: true} |
+------------------+
         |
         |
+------------------+
|  Wait for Next   |
|  Request         |
+------------------+
```
