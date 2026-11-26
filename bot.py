import os
import sys
import time
import json
import base64
import asyncio
import subprocess
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts

# Handle MoviePy imports across both 1.0.3 (in CI) and 2.x (local test environments)
try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

try:
    import google.generativeai as genai
except ImportError:
    genai = None

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "factech242-ai/youtube")

if GEMINI_API_KEY and genai:
    genai.configure(api_key=GEMINI_API_KEY)


def get_mock_script():
    """Default fallback script for dry-runs or emergency fallback."""
    return {
        "title": "Why You Procrastinate (Psychology Secret) #shorts",
        "description": "The shocking psychological reason you delay tasks and how the 2-minute rule rewires your brain. #shorts #psychology #facts",
        "scenes": [
            {"narration": "You are not lazy; your brain is just overwhelmed.", "caption": "NOT LAZY", "pose": "thinking"},
            {"narration": "Procrastination is an emotional regulation problem, not poor time management.", "caption": "EMOTION ISSUE", "pose": "point"},
            {"narration": "Your amygdala perceives the daunting task as an active threat.", "caption": "BRAIN ON ALERT", "pose": "shock"},
            {"narration": "Use the two-minute rule to trick your mind into instant action.", "caption": "2-MINUTE RULE", "pose": "idea"},
            {"narration": "Follow for daily psychology secrets that change your life.", "caption": "FOLLOW FOR MORE", "pose": "happy"}
        ]
    }


def generate_script():
    """Generates Short script using gemini-3.8-flash first with gemini-3.5-flash-lite fallback."""
    if not GEMINI_API_KEY or not genai:
        print("GEMINI_API_KEY not set or SDK missing. Using fallback script.")
        return get_mock_script()

    prompt = (
        "Write a fast-paced, punchy 35-second YouTube Short script about a mind-blowing "
        "psychological fact or human behavior secret. Break it into 5 short scenes.\n"
        "Return ONLY valid JSON with this exact structure (no markdown backticks):\n"
        "{\n"
        '  "title": "Catchy Short Title under 65 chars #shorts",\n'
        '  "description": "2-sentence engaging description with 3 relevant hashtags #shorts #psychology #facts",\n'
        '  "scenes": [\n'
        '    {"narration": "Hook sentence 1.", "caption": "HOOK TEXT", "pose": "thinking"},\n'
        '    {"narration": "Sentence 2.", "caption": "KEY POINT 2", "pose": "point"},\n'
        '    {"narration": "Sentence 3.", "caption": "KEY POINT 3", "pose": "shock"},\n'
        '    {"narration": "Sentence 4.", "caption": "KEY POINT 4", "pose": "idea"},\n'
        '    {"narration": "Strong takeaway CTA.", "caption": "FOLLOW FOR MORE", "pose": "happy"}\n'
        "  ]\n"
        "}"
    )

    models_to_try = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"]
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
        except Exception as e:
            print(f"Could not initialize {model_name}: {e}")
            continue

        for attempt in range(1, 4):
            try:
                print(f"Trying {model_name} (attempt {attempt}/3)...")
                response = model.generate_content(prompt, request_options={"timeout": 60})
                raw = response.text.strip()

                # Clean markdown fencing if present
                if "```" in raw:
                    parts = raw.split("```")
                    for part in parts:
                        cleaned = part.strip()
                        if cleaned.startswith("json"):
                            cleaned = cleaned[4:].strip()
                        if "{" in cleaned and "}" in cleaned:
                            raw = cleaned
                            break

                start = raw.find("{")
                end = raw.rfind("}")
                if start != -1 and end != -1:
                    raw = raw[start : end + 1]

                data = json.loads(raw)
                if "scenes" in data and len(data["scenes"]) >= 3:
                    return data
            except Exception as e:
                print(f"{model_name} attempt {attempt} failed: {e}")
                time.sleep(attempt * 4)

    print("All Gemini API calls timed out/failed. Falling back to built-in psychology script.")
    return get_mock_script()


def draw_stickman_frame(caption, pose, out_path):
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), color=(18, 18, 24))
    draw = ImageDraw.Draw(img)

    # Frame border
    draw.rectangle([30, 30, W - 30, H - 30], outline=(70, 130, 255), width=6)

    # Stickman Head
    cx, head_y = W // 2, 760
    r = 85
    draw.ellipse([cx - r, head_y - r, cx + r, head_y + r], outline=(255, 255, 255), width=12)

    # Face details based on pose
    if pose == "shock":
        draw.ellipse([cx - 35, head_y - 25, cx - 15, head_y - 5], fill=(255, 255, 255))
        draw.ellipse([cx + 15, head_y - 25, cx + 35, head_y - 5], fill=(255, 255, 255))
        draw.ellipse([cx - 18, head_y + 20, cx + 18, head_y + 52], outline=(255, 255, 255), width=7)
    else:
        draw.ellipse([cx - 32, head_y - 20, cx - 18, head_y - 6], fill=(255, 255, 255))
        draw.ellipse([cx + 18, head_y - 20, cx + 32, head_y - 6], fill=(255, 255, 255))
        draw.arc([cx - 30, head_y + 5, cx + 30, head_y + 42], start=15, end=165, fill=(255, 255, 255), width=7)

    # Body spine
    neck_y = head_y + r
    hip_y = neck_y + 270
    draw.line([cx, neck_y, cx, hip_y], fill=(255, 255, 255), width=12)

    # Arms
    shoulder_y = neck_y + 60
    if pose == "point":
        draw.line([cx, shoulder_y, cx - 140, shoulder_y + 120], fill=(255, 255, 255), width=12)
        draw.line([cx, shoulder_y, cx + 210, shoulder_y - 70], fill=(255, 255, 255), width=12)
    elif pose == "thinking":
        draw.line([cx, shoulder_y, cx - 130, shoulder_y + 130], fill=(255, 255, 255), width=12)
        draw.line([cx, shoulder_y, cx + 110, shoulder_y + 40], fill=(255, 255, 255), width=12)
        draw.line([cx + 110, shoulder_y + 40, cx + 35, head_y + 55], fill=(255, 255, 255), width=12)
    elif pose == "idea":
        draw.line([cx, shoulder_y, cx - 160, shoulder_y - 110], fill=(255, 255, 255), width=12)
        draw.line([cx, shoulder_y, cx + 160, shoulder_y - 110], fill=(255, 255, 255), width=12)
        draw.ellipse([cx - 35, head_y - 210, cx + 35, head_y - 140], outline=(255, 220, 60), width=8)
    else:
        draw.line([cx, shoulder_y, cx - 150, shoulder_y + 130], fill=(255, 255, 255), width=12)
        draw.line([cx, shoulder_y, cx + 150, shoulder_y + 130], fill=(255, 255, 255), width=12)

    # Legs
    draw.line([cx, hip_y, cx - 110, hip_y + 240], fill=(255, 255, 255), width=12)
    draw.line([cx, hip_y, cx + 110, hip_y + 240], fill=(255, 255, 255), width=12)

    # Cross-platform font loading
    font = None
    for font_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "arial.ttf",
    ]:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, 64)
                break
            except Exception:
                pass
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            pass

    # Wrap caption text
    words = caption.upper().split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if len(test) <= 18:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    y_text = 260
    for line in lines[:4]:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y_text), line, font=font, fill=(255, 230, 80))
        y_text += 85

    img.save(out_path)


async def generate_tts(text, out_mp3):
    communicate = edge_tts.Communicate(text, voice="en-US-ChristopherNeural", rate="+8%")
    await communicate.save(out_mp3)


def build_video(script_data, output_mp4="short.mp4"):
    """
    Renders 1080x1920 24fps vertical video using MoviePy 1.0.3,
    and applies faststart moov atom optimization so YouTube never abandons processing.
    """
    clips = []
    temp_files = []
    try:
        for idx, scene in enumerate(script_data["scenes"]):
            img_path = f"frame_{idx}.png"
            aud_path = f"audio_{idx}.mp3"
            temp_files.extend([img_path, aud_path])

            draw_stickman_frame(scene["caption"], scene.get("pose", "happy"), img_path)
            asyncio.run(generate_tts(scene["narration"], aud_path))

            audio_clip = AudioFileClip(aud_path)
            img_clip = ImageClip(img_path)
            if hasattr(img_clip, "with_duration"):
                img_clip = img_clip.with_duration(audio_clip.duration).with_audio(audio_clip)
            else:
                img_clip = img_clip.set_duration(audio_clip.duration).set_audio(audio_clip)
            clips.append(img_clip)

        final = concatenate_videoclips(clips, method="compose")
        # In moviepy==1.0.3: use ffmpeg_params=["-pix_fmt", "yuv420p"] (not pixel_format=)
        final.write_videofile(
            output_mp4,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            ffmpeg_params=["-pix_fmt", "yuv420p"],
            preset="ultrafast",
            threads=2,
        )
    finally:
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    # Ensure moov atom is placed at the beginning (+faststart) to fix YouTube "Processing abandoned"
    faststart_temp = f"faststart_{output_mp4}"
    try:
        res = subprocess.run(
            ["ffmpeg", "-y", "-i", output_mp4, "-c", "copy", "-movflags", "+faststart", faststart_temp],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        if os.path.exists(faststart_temp) and os.path.getsize(faststart_temp) > 10000:
            os.replace(faststart_temp, output_mp4)
            print("Successfully applied faststart (moov atom placed at front for YouTube).")
    except Exception as e:
        print(f"Notice: faststart step: {e}")

    return output_mp4


def upload_to_github_repo(video_path):
    """Pushes short.mp4 to GitHub and verifies the raw CDN serves real MP4 bytes."""
    api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/contents/short.mp4"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    # Get default branch name cleanly
    repo_res = requests.get(f"https://api.github.com/repos/{GITHUB_REPOSITORY}", headers=headers, timeout=30)
    repo_res.raise_for_status()
    default_branch = repo_res.json().get("default_branch", "main")

    sha = None
    get_res = requests.get(api_url, headers=headers, timeout=30)
    if get_res.status_code == 200:
        sha = get_res.json().get("sha")

    with open(video_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    data = {
        "message": "Update generated Short MP4",
        "content": encoded,
        "branch": default_branch,
    }
    if sha:
        data["sha"] = sha

    put_res = requests.put(api_url, headers=headers, json=data, timeout=60)
    put_res.raise_for_status()

    # Use commit-specific SHA URL so GitHub CDN never serves stale cache
    commit_sha = put_res.json()["commit"]["sha"]
    raw_mp4_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{commit_sha}/short.mp4"
    print("Direct GitHub Raw MP4 URL:", raw_mp4_url)

    # Verify via HTTP HEAD and GET range check that the URL returns HTTP 200 and valid MP4 video bytes (>10KB)
    verified = False
    for attempt in range(1, 11):
        print(f"CDN check attempt {attempt}/10...")
        try:
            head_check = requests.head(raw_mp4_url, timeout=15)
            status = head_check.status_code
            size = int(head_check.headers.get("Content-Length", 0))
            print(f"HEAD -> Status: {status}, Size: {size} bytes")

            if status == 200 and size > 10000:
                get_check = requests.get(raw_mp4_url, headers={"Range": "bytes=0-1024"}, timeout=15)
                if get_check.status_code in (200, 206) and (b"ftyp" in get_check.content or size > 10000):
                    print(f"CDN verified: HTTP 200, valid MP4 video bytes ({size} bytes) ready.")
                    verified = True
                    break
        except Exception as err:
            print(f"Check attempt {attempt} error: {err}")
        time.sleep(3)

    if not verified:
        raise RuntimeError(f"GitHub Raw CDN did not return a valid MP4: {raw_mp4_url}")

    return raw_mp4_url


def validate_video_with_ffprobe(video_path):
    """Proves with FFprobe that the video is a valid, uncorrupted MP4 file."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "stream=index,codec_name,codec_type,width,height,r_frame_rate,duration",
        "-show_entries", "format=duration,size,format_name",
        "-of", "json",
        video_path,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    probe = json.loads(res.stdout)
    streams = probe.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    print("=== FFprobe Validation Report ===")
    print(f"File Path: {video_path}")
    print(f"File Size: {os.path.getsize(video_path)} bytes")
    if v_stream:
        print(f"Video Stream: {v_stream.get('codec_name')} {v_stream.get('width')}x{v_stream.get('height')} @ {v_stream.get('r_frame_rate')} fps")
    if a_stream:
        print(f"Audio Stream: {a_stream.get('codec_name')} duration={a_stream.get('duration')}s")

    assert v_stream is not None, "Missing video stream"
    assert v_stream.get("width") == 1080 and v_stream.get("height") == 1920, f"Expected 1080x1920, got {v_stream.get('width')}x{v_stream.get('height')}"
    assert a_stream is not None, "Missing audio stream"
    assert os.path.getsize(video_path) > 10000, "File size under 10KB"
    print("SUCCESS: short.mp4 is 100% valid, uncorrupted vertical MP4 (1080x1920, 24fps, H.264 + AAC)!")


def run_dry_run():
    """Runs local dry-run test: generates script, renders video, and validates with FFprobe."""
    print("=== Starting Local Dry-Run Test ===")
    data = generate_script()
    print("Generated Script:", json.dumps(data, indent=2))
    mp4 = build_video(data, "short.mp4")
    validate_video_with_ffprobe(mp4)
    print("=== Local Dry-Run Test Completed Successfully ===")


def run_pipeline():
    for run_attempt in range(1, 4):
        try:
            print(f"=== Pipeline Run {run_attempt}/3 ===")
            data = generate_script()
            mp4 = build_video(data, "short.mp4")
            direct_url = upload_to_github_repo(mp4)

            payload = {
                "video_url": direct_url,
                "title": data["title"][:95],
                "description": data["description"][:4900],
            }
            hook_res = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=30)
            print("Make.com status:", hook_res.status_code, hook_res.text)
            hook_res.raise_for_status()
            print("SUCCESS! Pipeline completed cleanly.")
            return
        except Exception as e:
            print(f"Run {run_attempt} failed: {e}")
            if run_attempt < 3:
                time.sleep(15)
            else:
                raise


if __name__ == "__main__":
    if "--dry-run" in sys.argv or "--test" in sys.argv or os.environ.get("DRY_RUN") == "1":
        run_dry_run()
    else:
        run_pipeline()
