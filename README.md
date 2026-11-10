# CINEFORGE

A local website that turns a **title** or a **video link** into a finished YouTube video: script, each movie's trailer, voice, mood music, edit, posters, review, upload. Everything is set on the **Settings** page; no file editing needed.

## Upload accounts (Settings > Upload accounts)
- **YouTube:** upload your `client_secret.json` (OAuth client of type "Desktop app") on that page, press **Connect YouTube**, and sign in with the channel's Google account in the window that opens on your PC. No terminal needed. Disconnect any time.
- **Facebook and Instagram:** Page token, Page ID and Instagram ID, with a **Test connection** button (steps further down).
- **Publish defaults:** which platforms are ticked by default and the default YouTube privacy.
- The sidebar shows a green dot for each platform that is connected.

## Footage and ideas
- **One movie, long video:** besides the trailer, the app adds up to 2 official clips or featurettes from the studio or a licensed clip channel (for example Movieclips), so there are real scenes and not only the trailer. Turn off with "One-movie long videos: add the studio's official clips".
- **Lists (movie recommendations):** trailers, as before.
- **Shorts:** an official vertical 1080p clip if one exists, else the 16:9 trailer zoomed to fill the screen.
- **Popular videos on your topic** (titles, view counts, links) are listed on the project page as ideas for the hook. They are never downloaded or used as footage.

## Latest changes
- **1080p trailers and vertical Shorts.** In Settings > Picture and hook, set "Best trailer quality to download" to 1080p to always use 1080p trailers. For Shorts, the app first looks for an official vertical (9:16) clip of each movie. It is only used if it is real 1080p quality (1080 wide); otherwise the normal 16:9 trailer is used, zoomed to fill the Short. Long videos always use 16:9 sources.
- **Music that fits the mood.** Order: your own tracks in `assets/music/<mood>/` (for example `horror`), then free no-attribution tracks (CC0 / public domain) downloaded once from Openverse and kept in that folder as `auto_...` (delete any you dislike), then a soft generated pad. Change the order in Settings > Audio mix > Background music source.
- **The movie's name is clear.** Each movie gets a title card on screen (number, name, year) when its part starts, and the narration says the name first. The first shot of each movie's part is the best scene found for it.
- **Simple words.** The writer uses common words anyone can understand, short sentences, no idioms or slang.
- **Progress and video under the project.** Click a project in Projects: its progress, and later its video and publish box, open right below it. Click again to close.

## What is new in this version
- **Stronger hook.** The writer drafts 3 hook options with different formulas (cold open, chilling question, direct challenge, surprising true detail) and uses the best. It also reads what is already popular on the topic (titles and view counts of top videos, no AI request) to pick angles that earn views, always writing original wording. The first seconds use the strongest trailer scenes, cut fast, with a short bass hit on the first frame, and the hook line is shown big and yellow in the middle of the screen.
- **Tone follows the title.** The writer decides the mood first (comedy is hilarious, mystery and suspense slow-burn, thriller urgent, horror creeping dread, and so on). The same mood sets the voice emotions, the music and the kind of opening scene.
- **Lengths.** List Shorts end within 30 s (about 62 words), one-movie Shorts within 20 s (about 44 words), long videos within 2-3 minutes (about 360 words). If the voice runs longer, it is sped up (at most 1.2x) to fit, and a warning is shown if it still does not.
- **One movie = told by the main character.** In first person, present tense, using only true events and no ending. If there is no clear main character, it becomes curiosity-driven narration. With the free voices, a female protagonist gets the female voice.
- **One-click publishing** to YouTube, Instagram (Reels) and Facebook (Page Reels, or a Page video for long videos). Each platform gets its own title or caption and hashtags, written in the same script request. A lighter 1080p copy is sent to Instagram and Facebook. One platform failing does not stop the others.
- **Picture quality.** Trailers are downloaded in up to 4K (setting), lower-quality sources are upscaled to at least 1080p, and the finished video is upsized once at the end. See Settings > Picture and hook.

## Publishing to Instagram and Facebook: setup
You need a Facebook Page, an Instagram Professional (Creator or Business) account linked to that Page, and a Meta developer app (developers.facebook.com).
1. Create a Business app and add the Instagram and Facebook Login products.
2. In the Graph API Explorer, pick your app and generate a token with these permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `publish_video`, `instagram_basic`, `instagram_content_publish`.
3. Turn it into a long-lived token, then call `/me/accounts` to get your **Page ID** and a **Page access token** (one made from a long-lived user token does not expire).
4. Get the Instagram ID with `/<page-id>?fields=instagram_business_account`.
5. Paste the token, Page ID and Instagram ID in Settings > Social accounts and press **Test connection**.
Notes: this code follows Meta's documented Reels upload flows but could not be tested against Meta from where it was built, so test with one private or small post first. Meta changes things often: if it says the API version is too old, set a newer one in Settings. For your own accounts, an app in development mode normally works without app review. Instagram allows about 100 API posts a day and Facebook about 30 Reels a day. Instagram is Shorts only (Reels are vertical).

---

## Quick start
1. Install Python 3.10+ and FFmpeg (`winget install Gyan.FFmpeg` on Windows).
2. `python -m venv venv`, activate it, then `python -m pip install -r requirements.txt`.
3. `python run.py`, open http://127.0.0.1:8000, go to **Settings**, add your keys, press **Save and test** on each AI.
4. Make a video from **New video**.

## The four keys you asked for
Paste them on the Settings page (or into `.env`):
- `GROQ_API_KEY` and `GROQ_MODEL`
- `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`
- `ANTHROPIC_API_KEY` (model is pre-filled)
- `PIXABAY_API_KEY`
Order of AI writers: `LLM_PROVIDERS=gemini,groq,openrouter,anthropic` (free first, Claude last). A provider with no key or model is skipped. Models change often: press **Load models** on a provider's card to see what your key can use. A provider whose model cannot read images is skipped for scene analysis and the next one is tried.

## The hook (first 4-5 seconds)
For each trailer, one AI request scores every scene for how scroll-stopping it is (close-ups, chemistry and kisses, fights, shocks, big reveals) and flags nudity or explicit scenes, which are never used. The first `HOOK_SECONDS` of every video use the strongest scenes, cut fast, taken from all the movies in the video. Choose what counts as strong with `HOOK_STYLE`: balanced, romance, action, shock. Without AI descriptions, a cheap guess picks late, fast-cut scenes (trailers build to a climax). Suggestive hooks can get a video age-restricted or limited on ads and reach, so check YouTube's policies for your channel.

## Picture quality
Clips are cut at 1080p (fast) and the finished video is upsized once at the end with a high-quality scaler, light sharpening and sharp captions, then encoded at YouTube-friendly bitrates (about 40 Mbit/s at 4K). Uploading at 1440p or 4K makes YouTube use its better video encoding, so videos look sharper even though the trailers are 1080p sources (upsizing cannot add real detail). Defaults: Shorts 4K, long videos 1440p. A graphics card encoder (NVIDIA, Intel, AMD or Apple) is used automatically when it works. Rough CPU times on a weak one-core machine: 4K is about 4x slower than 1080p. On a normal multi-core PC a 40-second 4K Short renders in a minute or two.

## Saving AI requests (budget mode, on by default)
One request describes up to 16 trailer scenes and also scores the hook and checks safety; the poster ideas come with a click prediction (no separate ranking request); Shorts make no posters; scripts are rewritten at most once. The Usage page measures the real average requests per Short and per long video from your own history and has a **Daily plan** box to check a plan such as 5 Shorts a day against your limits.

## Rights
Trailers are copyrighted by the studios; short clips under your own commentary are a common use, not a guarantee. Expect possible Content ID claims. The app credits the studio and links the trailers in the description.

---

# YT Studio

A local website that turns a **title** or a **video link** into a finished YouTube video:

```
title / link -> script (Claude) -> narration (ElevenLabs) -> visuals (your library / Pexels)
             -> FFmpeg edit + captions + music -> 4 AI thumbnails (best one picked) -> review -> upload
```

Everything runs on your computer. Videos wait in a review queue and upload as **private** by default.

---

## Setup (about 15 minutes)

### 1. Install Python 3.10 or newer
Check with `python --version` (use `python3` on Mac/Linux). Get it from python.org if needed.

### 2. Install FFmpeg (required)
- **Windows:** `winget install Gyan.FFmpeg` (then reopen the terminal)
- **Mac:** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt install ffmpeg`

Check with `ffmpeg -version` and `ffprobe -version`.

### 3. Install the project
Open a terminal in this folder:

```bash
python -m venv venv
# Windows:      venv\Scripts\activate
# Mac/Linux:    source venv/bin/activate
pip install -r requirements.txt
```

### 4. Add your API keys (free setup)
Copy `.env.example` to `.env` (the file is already set up for the free route). Fill in two keys:

| `.env` line | Get it from | Cost |
|---|---|---|
| `GEMINI_API_KEY=` | aistudio.google.com > **Get API key** (sign in with Google) | Free, rate-limited |
| `PIXABAY_API_KEY=` | pixabay.com > sign up, then open pixabay.com/api/docs while logged in; your key is shown there | Free |
| `PEXELS_API_KEY=` (optional) | pexels.com/api (new keys were paused at the time of writing) | Free |

Leave everything else as it is. By default, voices come from `VOICE_PROVIDER=edge` (free, no key) and thumbnails are built from video frames.

If you get a "model not found" error, open AI Studio, copy a current Flash model name, and set `GEMINI_MODEL=` to it.

**Upgrading later (all optional):**
- Claude scripts: set `LLM_PROVIDER=anthropic` and fill `ANTHROPIC_API_KEY`
- ElevenLabs voice: set `VOICE_PROVIDER=elevenlabs` and fill `ELEVENLABS_API_KEY` (and `ELEVENLABS_VOICE_ID`)
- AI thumbnail art: fill `OPENAI_API_KEY`

### 5. Start it
```bash
python run.py
```
Open **http://127.0.0.1:8000**. The left panel shows which keys are detected.

Test first: make a Short from a title. With no ElevenLabs key it renders silent narration, so you can check the whole pipeline.

### 6. Connect YouTube (one time, only when you want uploads)
1. Go to console.cloud.google.com and create a project.
2. **APIs & Services > Library** > enable **YouTube Data API v3**.
3. **OAuth consent screen**: choose External, fill the basics, and under **Test users** add your own Google account.
4. **Credentials > Create credentials > OAuth client ID > Desktop app**. Download the JSON.
5. Save it in this folder as `client_secret.json`.
6. Run (with the venv active):
   ```bash
   python -m backend.app.pipeline.youtube
   ```
   A browser opens. Sign in with the account that owns your channel and approve. This creates `token.json`.
7. Restart `python run.py`. The panel now shows "YouTube upload" as connected.

**Things to know about uploads**
- Videos uploaded through an API project that Google has not audited are forced to **private**. Request an audit at support.google.com/youtube/contact/yt_api_form if you want public uploads straight from the tool. Until then, upload privately and switch visibility in YouTube Studio.
- Each upload costs about 1,600 quota units out of the default 10,000 per day (roughly 6 uploads a day).
- Custom thumbnails only work if your channel is verified (youtube.com/verify).
- Check "altered or synthetic content" in YouTube Studio if your video needs the disclosure (for example realistic synthetic voices or scenes).

---

## Using it

**From a title:** pick channel + format, type a topic, click *Create video*.
**From a link:** paste a link, tick the rights box, click *Create video*. The tool downloads the video (yt-dlp), reads its captions, splits it into scenes, describes each scene with a vision model, writes a new script, and reuses those scenes as footage.

Open **Projects** to watch progress. When a job reaches *ready to review* you can:
- play the video,
- edit title / description / tags,
- choose one of the 4 thumbnails (Claude marks the one it expects to perform best),
- upload as private, unlisted or public.

**Footage library:** upload clips and images you may use, with a one-line description of what is on screen. The editor matches script lines to descriptions. Better descriptions mean better matches.
**Music:** see "Movie trailers and background music" below.

---

## Shorts layout
In Shorts, landscape trailer footage is zoomed to fill 80% of the screen height (`SHORT_FILL=0.8` in `.env`; 1.0 = full screen) with a slow side-to-side pan, centred over a blurred backdrop. For Shorts the app first looks for an official vertical clip (a YouTube Short) of each movie (`PREFER_VERTICAL_TRAILERS=1`); if none is found it uses the normal trailer. Vertical clips fill the whole frame. Long videos are unchanged (16:9 as is). Zooming crops the sides of the picture, so very wide shots lose some of the edges.

## Voice (Eleven v4) and audio levels
Set `VOICE_PROVIDER=elevenlabs`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` and `ELEVENLABS_MODEL=eleven_v4`. The script writer gives each line an emotion (excited, curious, whispering, serious, sad, nervous, angry, laughing, sarcastic, calm) that is sent to v4 as an audio tag. Captions never show the tags. `ELEVENLABS_STABILITY` controls how emotional the delivery is (lower = more). If a voice ID comes from the Voice Library, add it to "My Voices" in ElevenLabs first.
The voice is levelled to `VOICE_LUFS` (default -15, loud and clear) and the music to the same level, then turned down to `MUSIC_VOLUME` (default 0.15 = 15%). Adjust those two lines in `.env` to taste.

## No repeated movies
Every movie used in a finished video is saved to a list (Projects > **Movies already used**). New scripts are told not to use those films, and the app checks the result: if the AI repeats one (or lists a film twice in one video), it asks again, up to 3 times, then stops with a clear message instead of making a repeat. Remakes with a different year count as different films. If you already posted videos before using this tool, paste those titles into that list (one per line). Untick **Avoid movies I've already covered** on the form when you deliberately want a specific film again. Note: the check compares titles, so the AI can still pick a *very similar* film; only exact titles are blocked.

## Movie trailers and background music

**Trailers.** For each movie in the script, the app finds its official trailer (TMDB if you add `TMDB_API_KEY`, otherwise a YouTube search), downloads it once (cached in `assets/trailers/`), cuts it into scenes, skips studio logos and the end title card, and fills each part of the script with that movie's scenes in order. When the script moves to the next movie, it switches to that movie's trailer. In Shorts, landscape footage keeps its full frame over a blurred background. Intro and outro lines use a taste of each trailer. If a trailer can't be found, that part falls back to your library / stock footage and a warning appears on the project page.

**Trailers are NOT copyright-free.** Studios own them. Short clips under your own commentary are a common use, but fair use is a judgement call, not a guarantee. Expect Content ID claims (often revenue goes to the studio) and possible restrictions. To lower the risk: keep the narration original and substantial, use only short clips, never upload a trailer as-is, and credit the studio (the app adds a credit and trailer links to the description automatically). Downloading from YouTube also goes against YouTube's terms. This is your decision and your channel's risk.

**Music by mood.** The script gets a mood (suspense, thriller, horror, action, drama, romance, scifi, comedy). The app picks a track from `assets/music/<mood>/` if you have put one there. If not, it generates a copyright-free ambient bed with FFmpeg that matches the mood (dark drone for suspense, heartbeat pulse for thriller, dissonant tones for horror, driving pulse for action, and so on). The generated beds are simple. For a more professional sound, drop tracks you have the rights to into the mood folders. Good free sources: the YouTube Audio Library, Pixabay Music, Free Music Archive. Check each track's licence and attribution rules.

## Rights: please read

The link feature is for videos **you own, have licensed, or that are Creative Commons / public domain**. Downloading someone else's film clips, trailers or videos and republishing them can get your channel strikes and demonetised, and it breaks YouTube's terms. The tool asks you to confirm rights and records each clip's source and licence on the project page. For movie content, the safe path is original commentary over footage you have permission to use (library + Pexels + your own screen-free graphics).

---

## Project layout

```
run.py                       start the server
channels.json                your channels (niche, default format, voice)
backend/app/main.py          API + serves the website
backend/app/worker.py        background job queue
backend/app/pipeline/
    ingest.py                yt-dlp download, captions, scene indexing
    script.py                Claude script writer
    voice.py                 ElevenLabs narration
    assets.py                scene matching (library, Pexels, fallback card)
    editor.py                FFmpeg timeline, captions, music
    thumbnails.py            4 concepts -> images -> ranking
    youtube.py               OAuth + upload
backend/app/static/          the website
assets/library, assets/music your footage and music
storage/                     jobs, outputs, database (safe to delete old jobs)
```

## Troubleshooting
- **"ffmpeg not found"**: install it (step 2) and reopen the terminal.
- **Script step fails**: check `ANTHROPIC_API_KEY`, and that `ANTHROPIC_MODEL` in `.env` is a model your account can use.
- **ElevenLabs 401/403**: wrong key, or the voice ID is not available on your plan.
- **Visuals are all plain colour cards**: add footage to the library or set `PEXELS_API_KEY`.
- **Thumbnails look like video frames**: add `OPENAI_API_KEY` for AI artwork.
- **Link download fails**: update yt-dlp (`pip install -U yt-dlp`); some videos block downloads.
- Failed jobs show the error on the project page; *Try again* re-runs from the start.

## Next upgrades
Swap the in-process queue for Celery + Redis, add scheduled publishing (`publishAt`), word-level caption timing from ElevenLabs timestamps, and `sentence-transformers` matching (`USE_EMBEDDINGS=1`).
#   R i z q - A I - V i d e o - A u t o m a t i o n  
 