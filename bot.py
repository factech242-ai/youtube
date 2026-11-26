import os
import json
import asyncio
import random
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
import google.generativeai as genai

# 1. Load GitHub Secrets
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MAKE_WEBHOOK_URL = os.environ["MAKE_WEBHOOK_URL"]

genai.configure(api_key=GEMINI_API_KEY)


def generate_script():
    """Generates a viral psychology/facts YouTube Short script via Gemini."""
    model = genai.GenerativeModel("gemini-2.5-flash")
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
    response = model.generate_content(prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def draw_stickman_frame(caption, pose, out_path):
    """Draws a clean 1080x1920 vertical stickman frame."""
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), color=(18, 18, 24))
    draw = ImageDraw.Draw(img)

    # Subtle accent border
    draw.rectangle([30, 30, W - 30, H - 30], outline=(70, 130, 255), width=6)

    # Stickman coordinates (centered)
    cx, head_y = W // 2, 760
    r = 85

    # Head
    draw.ellipse([cx - r, head_y - r, cx + r, head_y + r], outline=(255, 255, 255), width=12)

    # Eyes & expression
    if pose == "shock":
        draw.ellipse([cx - 35, head_y - 25, cx - 15, head_y - 5], fill=(255, 255, 255))
        draw.ellipse([cx + 15, head_y - 25, cx + 35, head_y - 5], fill=(255, 255, 255))
        draw.ellipse([cx - 18, head_y + 20, cx + 18, head_y + 52], outline=(255, 255, 255), width=7)
    else:
        draw.ellipse([cx - 32, head_y - 20, cx - 18, head_y - 6], fill=(255, 255, 255))
        draw.ellipse([cx + 18, head_y - 20, cx + 32, head_y - 6], fill=(255, 255, 255))
        draw.arc([cx - 30, head_y + 5, cx + 30, head_y + 42], start=15, end=165, fill=(255, 255, 255), width=7)

    # Torso
    neck_y = head_y + r
    hip_y = neck_y + 270
    draw.line([cx, neck_y, cx, hip_y], fill=(255, 255, 255), width=12)

    # Arms based on pose
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
        # Lightbulb circle above head
        draw.ellipse([cx - 35, head_y - 210, cx + 35, head_y - 140], outline=(255, 220, 60), width=8)
    else:
        draw.line([cx, shoulder_y, cx - 150, shoulder_y + 130], fill=(255, 255, 255), width=12)
        draw.line([cx, shoulder_y, cx + 150, shoulder_y + 130], fill=(255, 255, 255), width=12)

    # Legs
    draw.line([cx, hip_y, cx - 110, hip_y + 240], fill=(255, 255, 255), width=12)
    draw.line([cx, hip_y, cx + 110, hip_y + 240], fill=(255, 255, 255), width=12)

    # Bold caption at top
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
        preset="ultrafast",
        threads=2,
    )
    return output_mp4


def upload_and_trigger_make(video_path, title, description):
    """Uploads MP4 to tmpfiles.org, forces direct /dl/ link, and triggers Make.com."""
    with open(video_path, "rb") as f:
        res = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}, timeout=60)
    res.raise_for_status()
    raw_url = res.json()["data"]["url"]

    # Convert webpage URL to direct binary MP4 download URL
    direct_mp4_url = raw_url.replace("http://", "https://").replace("tmpfiles.org/", "tmpfiles.org/dl/")
    print("Direct MP4 URL:", direct_mp4_url)

    payload = {
        "video_url": direct_mp4_url,
        "title": title[:95],
        "description": description[:4900],
    }
    hook_res = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=30)
    print("Make.com status:", hook_res.status_code, hook_res.text)
    hook_res.raise_for_status()


if __name__ == "__main__":
    data = generate_script()
    mp4 = build_video(data, "short.mp4")
    upload_and_trigger_make(mp4, data["title"], data["description"])
