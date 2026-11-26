import os
import time
import json
import asyncio
import textwrap
import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from google import genai
from google.genai import types

# 1. Load Environment Variables
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MAKE_WEBHOOK_URL = os.environ["MAKE_WEBHOOK_URL"]


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

    models_to_try = [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.8-flash",
    ]

    for attempt, model_name in enumerate(models_to_try, start=1):
        try:
            print(f"Attempt {attempt} using {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.8,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Attempt {attempt} failed ({e}).")
            if attempt < len(models_to_try):
                wait_seconds = attempt * 15
                print(f"Waiting {wait_seconds} seconds before retrying...")
                time.sleep(wait_seconds)
            else:
                raise RuntimeError("All Gemini retry attempts failed due to server load.")


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
