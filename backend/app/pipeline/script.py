import re

from .. import config, llm, movies as movie_utils
from . import trends

SYSTEM = """You are the head writer for a YouTube movie channel. You write ORIGINAL narration:
opinionated, specific, and engaging. Never copy reviews, Wikipedia text, or another video's wording.
Add your own analysis, comparisons and a clear point of view so the video has real commentary value.
Be factually careful: if unsure about a detail (year, cast, plot point), leave it out instead of guessing.
Never claim to be a real person or invent real-life experiences.
LANGUAGE LEVEL: use simple, common words that anyone can understand, even people who are still learning the language (about A2-B1 level).
Short sentences. No idioms, no slang, no rare or literary words, no jargon. If a hard word is needed, say it in an easy way."""

TONE = """TONE MATCHING: first decide the genre mood from the title and the films, then write the WHOLE script in that tone.
comedy = hilarious: jokes, funny comparisons, exaggeration, playful roasting, a laugh in every part.
suspense or mystery = slow-burn tension: whispers, unanswered questions, clues, a creeping "something is wrong".
thriller = fast and urgent: ticking clock, danger, short breathless sentences.
horror = creeping dread: sensory fear, silence, "don't watch this alone".
action = punchy and high-energy: big verbs, momentum, adrenaline.
romance = warm and tender: butterflies, longing, a little swoon.
drama = heartfelt and emotional: a lump in the throat, human stakes.
scifi = awe and mind-bending "what if". If the title mixes genres, blend them, led by the first one named."""

HOOK_RULES = """The hook decides whether people stay. Write 3 options with different formulas, then use the strongest as the first segment:
(a) a cold open inside the most intense moment of the film, present tense;
(b) a chilling or irresistible question about the film's premise;
(c) a direct challenge to the viewer ("Don't press play if...") tied to the film;
(d) a surprising, specific, TRUE detail.
No greeting, no "in this video". The first three words must create tension or curiosity. Concrete beats vague. It must match the mood
and make the viewer need the answer. Never invent facts: if unsure, use a question or the film's own premise."""

POV_RULES = """ONE-MOVIE VIDEO (POV): speak AS the film's main character, in the first person, present tense, as if the viewer is inside their head
and their fear, joy or doubt is real. Use only events that truly happen in the film, nothing invented, and nothing from the ending.
If the film has no single clear main character (ensemble, documentary, anthology, animation with many leads), set pov to "narrator" and
write curiosity-driven narration instead. Also set "protagonist" (the character's name) and "gender" (male or female)."""

HINGLISH = """LANGUAGE: write in natural HINGLISH, the way young Indians really talk: Hindi in Roman letters mixed with the
English words people actually use (movie, scene, climax, twist, villain, hero, mast, full on). Not pure/formal Hindi, not full English.
Short sentences, desi humor and references (chai, cricket, IPL, 90s nostalgia, college life, shaadi, family drama), friendly 'tu/tum/aap'
tone like a cool older brother. No abuse, no vulgar words. "narration" = Hinglish in Roman letters (it is shown as captions).
"speech" = the SAME sentence for the voice: Devanagari Hindi, with common English words written in Devanagari too
(क्लाइमैक्स, ट्विस्ट, सीन); movie titles stay in Latin letters. Titles, descriptions, captions and hashtags are Hinglish in Roman letters;
tags mix English and Hindi search terms (for example 'best movies hindi', 'movie recommendation hindi')."""


def is_hinglish(language):
    l = (language or "").lower()
    return "hing" in l or l in ("hindi", "hi")


def _system(language="English", rules="multi", one_movie=False):
    """Built-in writer rules + the channel owner's rules from Settings (script_rules*.txt)."""
    path = {"single": config.SCRIPT_RULES_SINGLE_FILE, "long": config.SCRIPT_RULES_LONG_FILE}.get(rules, config.SCRIPT_RULES_FILE)
    try:
        extra = path.read_text(encoding="utf-8").strip()
    except OSError:
        extra = ""
    out = SYSTEM + "\n\n" + TONE
    if is_hinglish(language):
        out += "\n\n" + HINGLISH
    if one_movie:
        out += "\n\n" + POV_RULES
    return out + (f"\n\nExtra rules from the channel owner (follow these closely):\n{extra}" if extra else "")


def looks_single(title):
    """Guess from the title whether the video is about ONE film ('best thriller movie to watch tonight')."""
    t = (title or "").lower()
    plural = r"\b(movies|films|filmein|filmen|thrillers|horrors|comedies|dramas|series|picks|list|ranking|top)\b"
    if re.search(r"\b(one|1|ek|single)\b", t) and not re.search(plural, t):
        return True
    if re.search(r"\b([2-9]|\d{2,}|two|three|four|five|six|seven|eight|nine|ten)\b", t) or re.search(plural, t):
        return False
    return bool(re.search(r"\b(movie|film|picture|thriller|horror|drama)\b", t))


def generate_script(title, fmt, language, niche, context=None, source_scenes=None, avoid=None, movie_mode="auto"):
    f = config.FORMATS[fmt]
    ctx = ""
    if context:
        ctx = ("\n\nSOURCE MATERIAL (for facts only; do not copy its wording)\n"
               f"Title: {context.get('title')}\nDescription: {context.get('description')}\n"
               f"Transcript excerpt: {context.get('transcript', '')[:6000]}")
    scene_hint = ""
    if source_scenes:
        examples = [s["description"] for s in source_scenes if s.get("description")][:25]
        if examples:
            scene_hint = "\n\nFOOTAGE AVAILABLE (write visual_query lines that can match these when natural):\n- " + "\n- ".join(examples)

    avoid = avoid or []
    one_movie = movie_mode == "one" or (movie_mode == "auto" and looks_single(title))
    single = fmt == "short" and one_movie  # the short, 3-part layout
    rules = "single" if single else ("long" if fmt == "long" else "multi")
    if single:
        f = dict(f)
        f.update(target_words=config.SINGLE_TARGET_WORDS, max_words=config.SINGLE_MAX_WORDS, segments=config.SINGLE_SEGMENTS,
                 length_text=f"vertical YouTube Short, about {round(config.SINGLE_TARGET_WORDS / 2.5)} seconds (never longer than {round(config.SINGLE_MAX_WORDS / 2.5)} seconds)")
        ctx += ("\n\nONE-MOVIE SHORT: the video is about exactly ONE film (the movies list has one item). "
                "Parts: 1 hook (movie null), 2 the film (movie = its exact title), 3 outro (movie null).")
    elif one_movie:
        ctx += "\n\nONE-MOVIE VIDEO: the video is about exactly ONE film (the movies list has one item)."
    hook_words = 8 if single else (9 if fmt == "short" else 16)
    hook_secs = round(hook_words / 2.5, 1)

    trend_entries = []
    if config.TREND_RESEARCH and not context:  # what is already popular on this topic (angles to learn from, never to copy)
        trend_entries = trends.viral_entries(title)
        trend = trends.as_text(trend_entries)
        if trend:
            ctx += ("\n\nWHAT ALREADY GOES VIRAL ON THIS TOPIC (learn which angles, questions and curiosity gaps earn views; "
                    "write an ORIGINAL hook, never copy their wording):\n" + trend)

    hinglish = is_hinglish(language)
    pov_fields = ('  "pov": "protagonist or narrator",\n  "protagonist": "the main character\'s name, or null",\n  "gender": "male or female",\n' if one_movie else "")
    speech_field = ('      "speech": "the same line for the voice: Devanagari Hindi, English words in Devanagari, movie titles in Latin letters",\n' if hinglish else "")
    schema = ('Return JSON:\n{\n'
              '  "title": "YouTube title, under 70 chars, includes the main keyword, curiosity-driven, never misleading",\n'
              '  "description": "YouTube description: line 1 = the hook, line 2 = what the video covers (keywords), then 3-5 hashtags",\n'
              '  "tags": ["10-15 search tags"],\n'
              '  "instagram_caption": "Instagram Reel caption: the hook line first, one line of curiosity, a question to comment, then 4-5 hashtags",\n'
              '  "facebook_title": "Facebook video title, under 80 chars",\n'
              '  "facebook_description": "Facebook description: 1-2 sentences of curiosity, then 2-3 hashtags",\n'
              '  "mood": "ONE of: suspense, thriller, horror, action, drama, romance, scifi, comedy (decide this FIRST from the title and the genre of the films; the script tone, voice emotions, music and opening scenes all follow it)",\n'
              + pov_fields +
              '  "hook_options": ["3 different opening lines, strongest first"],\n'
              '  "movies": [{"title": "exact official movie title", "year": 2019}],\n'
              '  "segments": [\n'
              '    {"movie": "exact title from the movies list, or null for the hook and outro",\n'
              '      "narration": "what the voice says (1-2 sentences)",\n' + speech_field +
              '      "emotion": "how the line is delivered, ONE of: excited, curious, whispering, serious, sad, nervous, angry, laughing, sarcastic, calm. Match the mood (comedy: excited/laughing/sarcastic; suspense or mystery: whispering/curious/nervous; thriller: serious/nervous; horror: whispering/nervous; action: excited/serious; romance: calm/curious; drama: sad/serious)",\n'
              '      "visual_query": "5-10 words describing the ideal shot (e.g. \'detective walking alone in rainy neon street at night\')"}\n'
              '  ]\n}\n')
    rule_text = (
        "Rules:\n"
        '- "movies" lists every film you discuss, in order, with its real release year (null if unsure). Only include real, well-known films you are sure exist.\n'
        '- A segment about a film sets "movie" to that film\'s title; keep all segments of one film together.\n'
        f"- HOOK = the FIRST segment (movie: null): at most {hook_words} words, spoken in about {hook_secs} seconds. {HOOK_RULES}\n"
        "- Every film: say its exact title in the first words, then ONE specific true detail that makes people curious about it, and leave one question unanswered. Never spoil the ending.\n"
        "- The LAST segment (movie: null): pay off the hook, then one question for the comments. Its last words must flow into the first words of the hook so the video loops.\n"
        "- visual_query describes a generic scene; never name actors.\n")

    def build(extra=""):
        banned = ""
        if avoid:
            lst = "; ".join(f"{m['title']} ({m['year']})" if m.get("year") else m["title"] for m in avoid[:600])
            banned = ("\n\nALREADY COVERED ON THIS CHANNEL. Do NOT pick, recommend, or compare against any of these films "
                      f"(choose different ones, ideally less obvious): {lst}")
        return (f"Channel niche: {niche}\nVideo topic/title: {title}\nLanguage: {language}\n"
                f"Format: {fmt} ({f['length_text']})\n"
                f"Target narration length: about {f['target_words']} words across {f['segments']} segments. Never exceed {f['max_words']} words in total.\n"
                f"{ctx}{scene_hint}{banned}{extra}\n\n{schema}{rule_text}")

    extra = ""
    tries = 2 if config.BUDGET_MODE else 3  # budget mode: at most one rewrite, to save AI requests
    for attempt in range(tries):
        data = llm.ask_json(_system(language, rules, one_movie), build(extra), max_tokens=8000)
        segs = [s for s in data.get("segments", []) if s.get("narration")]
        if not segs:
            raise RuntimeError("The script generator returned no segments. Try again.")
        data["segments"] = segs
        data["single"] = single
        data["trends"] = trend_entries[:5]
        data["one_movie"] = one_movie
        data["language"] = language
        data["movies"] = [m for m in data.get("movies", []) if isinstance(m, dict) and m.get("title")]
        bad = movie_utils.conflicts(data["movies"], avoid) if avoid or data["movies"] else []
        words = sum(len(x["narration"].split()) for x in segs)
        too_long = words > f["max_words"]
        if not bad and (not too_long or attempt == tries - 1):  # on the last try a slightly long script is better than none
            return data
        extra = ""
        if bad:
            extra += (f"\n\nYOUR LAST ANSWER REUSED THESE FILMS: {', '.join(bad)}. "
                      "Replace them with different films and make sure no film appears twice.")
        if too_long:
            extra += (f"\n\nYOUR LAST ANSWER WAS {words} WORDS, TOO LONG. Rewrite it at about {f['target_words']} words "
                      f"(hard maximum {f['max_words']}) by using shorter segments and fewer details.")
    raise RuntimeError("The AI kept choosing movies you have already covered or repeated one inside the video "
                       f"({', '.join(bad)}). Try again, or untick 'Avoid movies I've already covered'.")
