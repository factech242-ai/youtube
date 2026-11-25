import os
import json
import asyncio
import textwrap
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. Load & Verify Environment Variables
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
YOUTUBE_CLIENT_ID = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]


def generate_script():
    print("Generating script with Gemini...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = """
    Create a viral, punchy 3-scene YouTube Shorts script about a fascinating psychology fact, life hack, or mind-blowing science truth.
    Total spoken length must be under 45 seconds (around 70-90 words total).
    
    Return ONLY valid JSON with this exact structure:
    {
      "title": "Catchy YouTube Title under 60 chars #Shorts",
      "description": "Engaging 2-sentence description with relevant hashtags #Shorts #Facts #Psychology",
      "scenes": [
        {
          "narration": "Hook sentence spoken aloud.",
          "caption": "SHORT ON-SCREEN TEXT",
          "pose": "thinking"
        },
        {
          "narration": "Core explanation sentence spoken aloud.",
          "caption": "KEY INSIGHT TEXT",
          "pose": "explaining"
        },
        {
          "narration": "Mic-drop conclusion or twist.",
          "caption": "MIND-BLOWN TAKEAWAY",
          "pose": "celebrating"
        }
      ]
    }
    Valid values for "pose" are strictly: "thinking", "explaining", "celebrating", "shocked".
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
        ),
    )
    return json.loads(response.text)


async def generate_voiceover(text, output_path):
    communicate = edge_tts.Communicate(text, voice="en-US-ChristopherNeural", rate="+8%")
    await communicate.save(output_path)


def draw_stickman_frame(caption, pose, output_path):
    width, height = 1080, 1920
    img = Image.new("RGB", (width, height), color=(18, 18, 24))
    draw = ImageDraw.Draw(img)

    # Subtle accent border
    draw.rectangle([30, 30, width - 30, height - 30], outline=(60, 65, 85), width=6)

    # Stickman coordinates (centered lower-middle)
    cx, head_y = width // 2, 920
    head_r = 75
    neck_y = head_y + head_r
    hip_y = neck_y + 240
    line_color = (255, 255, 255)
    accent_color = (255, 215, 0)
    stroke = 14

    # Head
    draw.ellipse(
        [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
        outline=line_color,
        width=stroke,
    )

    # Eyes & Expression
    if pose == "shocked":
        draw.ellipse([cx - 32, head_y - 22, cx - 12, head_y - 2], fill=line_color)
        draw.ellipse([cx + 12, head_y - 22, cx + 32, head_y - 2], fill=line_color)
        draw.ellipse([cx - 18, head_y + 15, cx + 18, head_y + 48], outline=accent_color, width=8)
    elif pose == "thinking":
        draw.ellipse([cx - 30, head_y - 20, cx - 14, head_y - 4], fill=line_color)
        draw.ellipse([cx + 14, head_y - 20, cx + 30, head_y - 4], fill=line_color)
        draw.line([cx - 20, head_y + 28, cx + 22, head_y + 22], fill=line_color, width=8)
        # Question mark near head
        try:
            q_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
        except OSError:
            q_font = ImageFont.load_default()
        draw.text((cx + 105, head_y - 110), "?", fill=accent_color, font=q_font)
    else:
        draw.ellipse([cx - 30, head_y - 18, cx - 14, head_y - 2], fill=line_color)
        draw.ellipse([cx + 14, head_y - 18, cx + 30, head_y - 2], fill=line_color)
        draw.arc([cx - 28, head_y + 5, cx + 28, head_y + 42], start=15, end=165, fill=line_color, width=8)

    # Torso
    draw.line([cx, neck_y, cx, hip_y], fill=line_color, width=stroke)

    # Arms based on pose
    shoulder_y = neck_y + 45
    if pose == "celebrating":
        draw.line([cx, shoulder_y, cx - 130, shoulder_y - 130], fill=line_color, width=stroke)
        draw.line([cx, shoulder_y, cx + 130, shoulder_y - 130], fill=line_color, width=stroke)
    elif pose == "thinking":
        draw.line([cx, shoulder_y, cx - 110, shoulder_y + 110], fill=line_color, width=stroke)
        draw.line([cx, shoulder_y, cx + 95, shoulder_y + 30], fill=line_color, width=stroke)
        draw.line([cx + 95, shoulder_y + 30, cx + 35, head_y + 55], fill=line_color, width=stroke)
    elif pose == "shocked":
        draw.line([cx, shoulder_y, cx - 120, head_y - 10], fill=line_color, width=stroke)
        draw.line([cx, shoulder_y, cx + 120, head_y - 10], fill=line_color, width=stroke)
    else:  # explaining
        draw.line([cx, shoulder_y, cx - 135, shoulder_y + 60], fill=line_color, width=stroke)
        draw.line([cx, shoulder_y, cx + 145, shoulder_y - 50], fill=line_color, width=stroke)

    # Legs
    draw.line([cx, hip_y, cx - 95, hip_y + 230], fill=line_color, width=stroke)
    draw.line([cx, hip_y, cx + 95, hip_y + 230], fill=line_color, width=stroke)

    # Ground line
    draw.line([cx - 260, hip_y + 235, cx + 260, hip_y + 235], fill=(90, 95, 120), width=8)

    # Top Caption Text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
    except OSError:
        font = ImageFont.load_default()

    wrapped_lines = textwrap.wrap(caption.upper(), width=18)
    text_y = 320
    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(((width - text_w) // 2, text_y), line, fill=accent_color, font=font)
        text_y += 95

    img.save(output_path)


def build_video(script_data, output_video="short.mp4"):
    print("Rendering audio and stickman scenes...")
    clips = []

    for idx, scene in enumerate(script_data["scenes"]):
        audio_path = f"scene_{idx}.mp3"
        img_path = f"scene_{idx}.png"

        asyncio.run(generate_voiceover(scene["narration"], audio_path))
        draw_stickman_frame(scene["caption"], scene.get("pose", "explaining"), img_path)

        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration + 0.25

        img_clip = ImageClip(img_path).set_duration(duration).set_audio(audio_clip)
        clips.append(img_clip)

    final_video = concatenate_videoclips(clips, method="compose")
    final_video.write_videofile(
        output_video,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=4,
    )
    return output_video


def upload_to_youtube(video_path, title, description):
    print("Authenticating and uploading to YouTube...")
    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:95],
            "description": description,
            "tags": ["Shorts", "Facts", "Animation", "Stickman"],
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    print(f"Upload complete! Video ID: {response['id']}")


if __name__ == "__main__":
    data = generate_script()
    video_file = build_video(data)
    upload_to_youtube(video_file, data["title"], data["description"])
