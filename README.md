# YT Studio

**A local video-production workspace that turns a title or an eligible
video link into a ready-to-review YouTube video.**

YT Studio automates a video workflow on your computer: script
generation, narration, footage selection, editing, captions, background
music, thumbnail concepts, review, and YouTube upload.

Videos are placed in a review queue and are uploaded as **private by
default**.

> **Important:** Only use links and footage that you own, have licensed,
> or are otherwise permitted to use. Downloading and republishing
> someone else's content can violate copyright and platform terms.
-----------------------------------------------------------------------
## ScreenShots:
<img width="1917" height="805" alt="Screenshot 2026-11-12 120640" src="https://github.com/user-attachments/assets/c00ab63d-0a87-43ee-b771-953675ee39e9" />
<img width="1575" height="857" alt="Screenshot 2026-11-12 120726" src="https://github.com/user-attachments/assets/f318a3f5-3d5e-4530-80b6-a04716797492" />
<img width="1471" height="861" alt="Screenshot 2026-11-12 120716" src="https://github.com/user-attachments/assets/48df5744-a938-466f-82d1-00d5da520225" />
<img width="1821" height="863" alt="Screenshot 2026-11-12 120849" src="https://github.com/user-attachments/assets/04238b50-009d-46df-be86-7be11af9aae8" />
<img width="1515" height="841" alt="Screenshot 2026-11-12 130339" src="https://github.com/user-attachments/assets/d535603e-2331-4c21-abea-da3d683f3588" />
------------------------------------------------------------------------
## Project DEMO Link : https://youtu.be/tzGSdwBQ-KA
------------------------------------------------------------------------

## Contents

-   [Features](#features)
-   [Workflow](#workflow)
-   [Requirements](#requirements)
-   [Installation](#installation)
-   [Configuration](#configuration)
-   [Connect YouTube](#connect-youtube)
-   [Create and review a video](#create-and-review-a-video)
-   [Footage library and music](#footage-library-and-music)
-   [Shorts layout](#shorts-layout)
-   [Avoid repeating movies](#avoid-repeating-movies)
-   [Project structure](#project-structure)
-   [Troubleshooting](#troubleshooting)
-   [Known limitations and responsible
    use](#known-limitations-and-responsible-use)
-   [Potential next upgrades](#potential-next-upgrades)

## Features

-   Generate a video from a topic/title or a supported video link.
-   Write scripts with an LLM provider.
-   Generate narration using Microsoft Edge voices or ElevenLabs.
-   Match script lines to footage from your local library or Pexels.
-   Discover and download movie trailers where configured.
-   Edit video, captions, and music with FFmpeg.
-   Generate four thumbnail concepts and select a preferred option.
-   Review the finished video before uploading.
-   Keep a record of movies already used to reduce exact-title repeats.
-   Upload to YouTube using OAuth, with private visibility as the
    default workflow.

## Workflow

``` text
Title or eligible video link
          |
          v
      Script writing
          |
          v
   Voice narration
          |
          v
  Footage / scene matching
          |
          v
 FFmpeg edit + captions + music
          |
          v
   Thumbnail concepts
          |
          v
     Review queue
          |
          v
      YouTube upload
```

The application runs locally. Open the web interface after starting the
Python server.

## Requirements

-   Python 3.10 or newer
-   FFmpeg and FFprobe
-   Internet connection for AI/media APIs and YouTube uploads
-   API keys for the services you choose
-   A Google Cloud OAuth desktop client to enable YouTube uploads

### Install FFmpeg

Windows:

``` powershell
winget install Gyan.FFmpeg
```

macOS:

``` bash
brew install ffmpeg
```

Ubuntu/Debian:

``` bash
sudo apt install ffmpeg
```

Verify the installation:

``` bash
ffmpeg -version
ffprobe -version
```

## Installation

### 1. Create a virtual environment

``` bash
python -m venv venv
```

Activate it on Windows PowerShell:

``` powershell
.\venv\Scripts\Activate.ps1
```

On Windows Command Prompt:

``` bat
venv\Scripts\activate
```

On macOS/Linux:

``` bash
source venv/bin/activate
```

### 2. Install Python dependencies

``` bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example environment file:

``` bash
```

Then create `.env` from `.env.example` using your operating system's
file manager or shell. For example, on Windows:

``` powershell
Copy-Item .env.example .env
```

On macOS/Linux:

``` bash
cp .env.example .env
```

### 4. Start the application

``` bash
python run.py
```

Open:

``` text
http://127.0.0.1:8000
```

The left panel indicates which configured keys are detected.

## Configuration

### Basic/free configuration

The documented free-first setup uses:

  ----------------------------------------------------------------------------------------
  Environment variable    Purpose                 Notes
  ----------------------- ----------------------- ----------------------------------------
  `GEMINI_API_KEY`        Gemini script           Obtain a key from [Google AI
                          generation              Studio](https://aistudio.google.com/);
                                                  subject to account limits.

  `PIXABAY_API_KEY`       Pixabay media search    Obtain a key from [Pixabay
                                                  API](https://pixabay.com/api/docs/).

  `PEXELS_API_KEY`        Pexels media search     Optional; availability of new API keys
                                                  may vary.
  ----------------------------------------------------------------------------------------

By default, the documented setup uses:

``` env
VOICE_PROVIDER=edge
```

This uses Edge voices without an ElevenLabs API key. Thumbnail concepts
are built from video frames unless an AI image provider is configured.

If you receive a model-not-found error, check Google AI Studio for a
model currently available to your account and update:

``` env
GEMINI_MODEL=your_available_model
```

### Optional providers

  -----------------------------------------------------------------------
  Feature                             Configuration
  ----------------------------------- -----------------------------------
  Claude script generation            Set `LLM_PROVIDER=anthropic` and
                                      configure `ANTHROPIC_API_KEY`.

  ElevenLabs narration                Set `VOICE_PROVIDER=elevenlabs`,
                                      `ELEVENLABS_API_KEY`, and
                                      `ELEVENLABS_VOICE_ID`.

  ElevenLabs v4 model                 Set `ELEVENLABS_MODEL=eleven_v4`.

  AI thumbnail artwork                Configure `OPENAI_API_KEY`.

  Movie database lookup               Configure `TMDB_API_KEY` if
                                      available.
  -----------------------------------------------------------------------

For ElevenLabs, the configured voice ID must be available to your
account. If it comes from the Voice Library, add it to **My Voices**
first.

The writer can assign emotion tags such as excited, curious, whispering,
serious, sad, nervous, angry, laughing, sarcastic, or calm. These tags
are sent to ElevenLabs v4 when that provider is selected.

Voice loudness and music volume are configurable:

``` env
VOICE_LUFS=-15
MUSIC_VOLUME=0.15
```

A lower `ELEVENLABS_STABILITY` value produces a more expressive
delivery, according to the project's documented configuration.

**Keep API keys private.** Do not commit `.env`, OAuth credentials, or
access tokens to Git.

## Connect YouTube

You only need to complete this setup when you want to upload videos.

1.  Open [Google Cloud Console](https://console.cloud.google.com/) and
    create or select a project.

2.  Open **APIs & Services → Library** and enable **YouTube Data API
    v3**.

3.  Configure the OAuth consent screen. The documented setup uses
    External and adds your Google account under **Test users**.

4.  Open **Credentials → Create credentials → OAuth client ID**.

5.  Select **Desktop app** as the application type.

6.  Download the JSON credentials file.

7.  Save it in the project directory as `client_secret.json`.

8.  With the virtual environment active, run:

    ``` bash
    python -m backend.app.pipeline.youtube
    ```

9.  A browser window should open. Sign in with the Google account that
    owns the channel and approve access.

10. The authentication flow creates `token.json`. Restart the
    application:

``` bash
python run.py
```

The application should then show YouTube upload as connected.

### YouTube API considerations

-   Uploads from an API project that has not completed Google's required
    audit may be restricted to private visibility.
-   The documented default quota cost is approximately 1,600 units per
    upload against a default 10,000-unit daily quota. Check current
    Google documentation because quota rules can change.
-   Custom thumbnails require channel verification.
-   Review YouTube's altered or synthetic content disclosure
    requirements when applicable.

## Create and review a video

### Create from a title

1.  Open the creation form.
2.  Select a channel and video format.
3.  Enter a topic or title.
4.  Select **Create video**.

### Create from a link

1.  Paste a link to content you are authorized to use.
2.  Confirm the rights checkbox.
3.  Select **Create video**.

The documented link workflow uses `yt-dlp` to download the input, reads
available captions, splits the video into scenes, describes scenes with
a vision model, and writes a new script. It may reuse scenes as footage.
Use this only when you have the rights to do so.

### Review and publish

Open **Projects** and wait for the job to reach **Ready to review**. You
can then:

-   Play the rendered video.
-   Edit the title, description, and tags.
-   Choose from four thumbnail options.
-   Upload as private, unlisted, or public, subject to YouTube API
    restrictions and the application's available settings.

Review the complete video, metadata, thumbnail, and visibility before
uploading.

## Footage library and music

### Footage library

Upload clips and images to the local footage library. Add a one-line
description explaining what appears in each asset. The editor matches
script lines to these descriptions; clear, specific descriptions improve
matching.

### Movie trailers

When configured, the app looks for official trailers using TMDB or a
YouTube search, downloads them once, caches them in `assets/trailers/`,
and cuts them into scenes. The editor can skip studio logos and end
title cards.

If a trailer cannot be found, the relevant section falls back to library
or stock footage and a warning appears on the project page.

### Background music

The script assigns a mood, such as suspense, thriller, horror, action,
drama, romance, science fiction, or comedy. The app looks for a track
in:

``` text
assets/music/<mood>/
```

If no suitable track is available, it generates a simple ambient bed
with FFmpeg. For a more polished result, add music you have the rights
to use and check the licence and attribution terms for each track.

## Shorts layout

For Shorts, landscape trailer footage is adapted to a vertical frame
over a blurred background. The documented default is:

``` env
SHORT_FILL=0.8
PREFER_VERTICAL_TRAILERS=1
```

`SHORT_FILL` controls how much of the frame height the landscape footage
fills; `1.0` means full height. The app first looks for an official
vertical clip. If none is found, it uses the normal landscape trailer.
Cropping can remove content near the sides of wide shots.

Long videos remain in 16:9.

## Avoid repeating movies

The app records movie titles used in completed videos under **Projects →
Movies already used**. New scripts are instructed not to reuse those
titles, and the result is checked. If a repeat is detected, the script
may be regenerated up to three times before the job stops with a
message.

Remakes with different years count as different films. Add titles from
videos published before you started using the app, one title per line.
You can disable **Avoid movies I've already covered** when you
intentionally want to use a specific movie again.

The check is title-based; it does not guarantee that films with very
similar names or premises will be excluded.

## Project structure

The following layout is documented for the project:

``` text
run.py
channels.json
backend/
  app/
    main.py
    worker.py
    pipeline/
      ingest.py
      script.py
      voice.py
      assets.py
      editor.py
      thumbnails.py
      youtube.py
    static/
assets/
  library/
  music/
storage/
```

  --------------------------------------------------------------------------
  Path                                   Purpose
  -------------------------------------- -----------------------------------
  `run.py`                               Starts the local server.

  `channels.json`                        Channel configuration, including
                                         niche, default format, and voice.

  `backend/app/main.py`                  API and website serving.

  `backend/app/worker.py`                Background job queue.

  `backend/app/pipeline/ingest.py`       Link download, captions, and scene
                                         indexing.

  `backend/app/pipeline/script.py`       Script generation.

  `backend/app/pipeline/voice.py`        Narration generation.

  `backend/app/pipeline/assets.py`       Scene and footage matching.

  `backend/app/pipeline/editor.py`       FFmpeg timeline, captions, and
                                         music.

  `backend/app/pipeline/thumbnails.py`   Thumbnail concepts and selection.

  `backend/app/pipeline/youtube.py`      YouTube OAuth and upload.

  `backend/app/static/`                  Website assets.

  `assets/library/`, `assets/music/`     User footage and music.

  `storage/`                             Jobs, outputs, and database.
  --------------------------------------------------------------------------

Treat `storage/` as application data. Back it up before deleting
anything; do not assume all files there are disposable.

## Troubleshooting

  ------------------------------------------------------------------------
  Issue                               Suggested check
  ----------------------------------- ------------------------------------
  `ffmpeg not found`                  Install FFmpeg, reopen the terminal,
                                      and verify `ffmpeg -version`.

  Script generation fails             Check the configured provider key,
                                      model name, account access, and rate
                                      limits.

  ElevenLabs returns 401/403          Verify the API key and whether the
                                      voice ID is available on your plan.

  Visuals are plain colour cards      Add assets to the footage library or
                                      configure `PEXELS_API_KEY`.

  Thumbnails look like video frames   Configure `OPENAI_API_KEY` if AI
                                      artwork is desired.

  Link download fails                 Update `yt-dlp` with
                                      `python -m pip install -U yt-dlp`;
                                      some sources may block downloads.

  A job fails                         Read the error on the project page.
                                      The **Try again** action reruns the
                                      job from the start.
  ------------------------------------------------------------------------

## Known limitations and responsible use

### Copyright and platform terms

Movie trailers are generally copyrighted by their studios. Short clips
with original commentary may still receive Content ID claims,
restrictions, or takedowns. Fair use is a legal determination and is not
guaranteed by clip length, commentary, or attribution.

The link feature is intended for videos you own, have licensed, or are
permitted to use under an applicable licence, such as a valid Creative
Commons or public-domain source. Downloading someone else's video and
republishing it can violate copyright and YouTube's terms.

Before publishing:

-   Confirm that you have the necessary rights to every video, image,
    and audio asset.
-   Check the exact licence and attribution requirements.
-   Do not upload a trailer or third-party video as-is.
-   Make sure your narration and editing add original value.
-   Review YouTube's current copyright and synthetic-content policies.

### Generated content needs review

AI-generated scripts, scene descriptions, thumbnails, and metadata can
be inaccurate. Check factual claims, movie details, image suitability,
and the final edit yourself.

## Potential next upgrades

The supplied project notes identify these possible future improvements:

-   Replace the in-process queue with Celery and Redis.
-   Add scheduled publishing with `publishAt`.
-   Add word-level caption timing using ElevenLabs timestamps.
-   Add `sentence-transformers`-based scene matching with
    `USE_EMBEDDINGS=1`.

These are proposed upgrades, not claims that the features are already
implemented.
