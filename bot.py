import os
import json
import time
import asyncio
import subprocess
import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from google import genai

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
ZAPIER_WEBHOOK_URL = os.environ["ZAPIER_WEBHOOK_URL"]

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_script():
    prompt = (
        "Create a 35-second YouTube Short script about an interesting psychology "
        "or human behavior fact. Return ONLY valid JSON with these exact keys:\n"
        '{"title": "Catchy Short title under 60 chars #Shorts", '
        '"description": "2 sentence description with 3 relevant hashtags", '
        '"narration": "Engaging spoken voiceover script, 70 to 85 words, no emojis or stage directions"}'
    )
    models = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]

    for attempt in range(6):
        model_name = models[attempt % len(models)]
        try:
            print(f"Generating script with {model_name} (attempt {attempt + 1})...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            return json.loads(text.strip())
        except Exception as e:
            err = str(e)
            if "503" in err or "429" in err or "UNAVAILABLE" in err or "RESOURCE_EXHAUSTED" in err:
                print(f"{model_name} temporarily busy, retrying in 12 seconds...")
                time.sleep(12)
            else:
                raise
    raise RuntimeError("Gemini models remained busy after 6 attempts.")


async def create_voiceover(text, audio_path):
    communicate = edge_tts.Communicate(text, voice="en-US-ChristopherNeural", rate="+5%")
    await communicate.save(audio_path)


def draw_stickman_frame(narration, image_path):
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), color=(18, 20, 28))
    draw = ImageDraw.Draw(img)

    # Subtle accent border
    draw.rectangle([40, 40, width - 40, height - 40], outline=(0, 210, 255), width=6)

    # Draw Stickman character in upper-middle area
    cx, head_y = 540, 460
    # Head
    draw.ellipse([cx - 75, head_y - 75, cx + 75, head_y + 75], outline=(255, 255, 255), width=10)
    # Eyes
    draw.ellipse([cx - 32, head_y - 20, cx - 16, head_y - 4], fill=(0, 210, 255))
    draw.ellipse([cx + 16, head_y - 20, cx + 32, head_y - 4], fill=(0, 210, 255))
    # Smile
    draw.arc([cx - 30, head_y - 5, cx + 30, head_y + 35], start=15, end=165, fill=(255, 255, 255), width=6)
    # Body
    draw.line([cx, head_y + 75, cx, head_y + 310], fill=(255, 255, 255), width=10)
    # Arms (pointing/explaining pose)
    draw.line([cx, head_y + 130, cx - 130, head_y + 230], fill=(255, 255, 255), width=10)
    draw.line([cx, head_y + 130, cx + 140, head_y + 80], fill=(255, 255, 255), width=10)
    # Legs
    draw.line([cx, head_y + 310, cx - 95, head_y + 490], fill=(255, 255, 255), width=10)
    draw.line([cx, head_y + 310, cx + 95, head_y + 490], fill=(255, 255, 255), width=10)

    # Load font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except Exception:
        font = ImageFont.load_default()

    # Wrap narration text cleanly onto frame
    words = narration.split()
    lines, current_line = [], []
    for word in words:
        current_line.append(word)
        if len(" ".join(current_line)) > 28:
            lines.append(" ".join(current_line[:-1]))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    y_text = 1040
    for line in lines[:12]:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(((width - text_w) // 2, y_text), line, fill=(245, 245, 245), font=font)
        y_text += 62

    img.save(image_path)


def render_video(image_path, audio_path, video_path):
    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        video_path,
    ]
    subprocess.run(cmd, check=True)


def send_to_zapier(title, description, video_path):
    print("Sending video to Zapier webhook...")
    with open(video_path, "rb") as f:
        response = requests.post(
            ZAPIER_WEBHOOK_URL,
            data={"title": title, "description": description},
            files={"video": ("short.mp4", f, "video/mp4")},
            timeout=120,
        )
    print("Zapier status:", response.status_code, response.text)
    response.raise_for_status()


def main():
    data = generate_script()
    title = data["title"]
    description = data["description"]
    narration = data["narration"]

    print("Title:", title)
    asyncio.run(create_voiceover(narration, "voice.mp3"))
    draw_stickman_frame(narration, "frame.png")
    render_video("frame.png", "voice.mp3", "short.mp4")
    send_to_zapier(title, description, "short.mp4")
    print("Done! Short sent to Zapier successfully.")


if __name__ == "__main__":
    main()
