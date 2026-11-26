import os
import time
import json
import base64
import asyncio
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
import google.generativeai as genai

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MAKE_WEBHOOK_URL = os.environ["MAKE_WEBHOOK_URL"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]

genai.configure(api_key=GEMINI_API_KEY)


def generate_script():
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

    for model_name in ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash"]:
        model = genai.GenerativeModel(model_name)
        for attempt in range(1, 4):
            try:
                print(f"Trying {model_name} (attempt {attempt}/3)...")
                response = model.generate_content(prompt, request_options={"timeout": 60})
                raw = response.text.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                return json.loads(raw.strip())
            except Exception as e:
                print(f"{model_name} attempt {attempt} failed: {e}")
                time.sleep(attempt * 5)

    raise RuntimeError("All Gemini models failed.")


def draw_stickman_frame(caption, pose, out_path):
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), color=(18, 18, 24))
    draw = ImageDraw.Draw(img)

    draw.rectangle([30, 30, W - 30, H - 30], outline=(70, 130, 255), width=6)

    cx, head_y = W // 2, 760
    r = 85
    draw.ellipse([cx - r, head_y - r, cx + r, head_y + r], outline=(255, 255, 255), width=12)

    if pose == "shock":
        draw.ellipse([cx - 35, head_y - 25, cx - 15, head_y - 5], fill=(255, 255, 255))
        draw.ellipse([cx + 15, head_y - 25, cx + 35, head_y - 5], fill=(255, 255, 255))
        draw.ellipse([cx - 18, head_y + 20, cx + 18, head_y + 52], outline=(255, 255, 255), width=7)
    else:
        draw.ellipse([cx - 32, head_y - 20, cx - 18, head_y - 6], fill=(255, 255, 255))
        draw.ellipse([cx + 18, head_y - 20, cx + 32, head_y - 6], fill=(255, 255, 255))
        draw.arc([cx - 30, head_y + 5, cx + 30, head_y + 42], start=15, end=165, fill=(255, 255, 255), width=7)

    neck_y = head_y + r
    hip_y = neck_y + 270
    draw.line([cx, neck_y, cx, hip_y], fill=(255, 255, 255), width=12)

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

    draw.line([cx, hip_y, cx - 110, hip_y + 240], fill=(255, 255, 255), width=12)
    draw.line([cx, hip_y, cx + 110, hip_y + 240], fill=(255, 255, 255), width=12)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    except Exception:
        font = ImageFont.load_default()

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
    clips = []
    for idx, scene in enumerate(script_data["scenes"]):
        img_path = f"frame_{idx}.png"
        aud_path = f"audio_{idx}.mp3"

        draw_stickman_frame(scene["caption"], scene.get("pose", "happy"), img_path)
        asyncio.run(generate_tts(scene["narration"], aud_path))

        audio_clip = AudioFileClip(aud_path)
        img_clip = ImageClip(img_path).set_duration(audio_clip.duration + 0.15).set_audio(audio_clip)
        clips.append(img_clip)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        output_mp4,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p"],
        preset="ultrafast",
        threads=2,
    )
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

    # Verify the URL returns HTTP 200 and real video bytes before triggering Make.com
    for _ in range(5):
        check = requests.head(raw_mp4_url, timeout=15)
        size = int(check.headers.get("Content-Length", 0))
        print(f"CDN check -> Status: {check.status_code}, Size: {size} bytes")
        if check.status_code == 200 and size > 10000:
            return raw_mp4_url
        time.sleep(3)

    raise RuntimeError(f"GitHub Raw CDN did not return a valid MP4: {raw_mp4_url}")


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
            print("SUCCESS! Everything completed cleanly.")
            return
        except Exception as e:
            print(f"Run {run_attempt} failed: {e}")
            if run_attempt < 3:
                time.sleep(15)
            else:
                raise


if __name__ == "__main__":
    run_pipeline()
