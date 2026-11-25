import os, json, asyncio, subprocess, textwrap, requests, edge_tts
from PIL import Image, ImageDraw, ImageFont
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompt = """
Pick one fascinating, lesser-known science or psychology fact for a 30-second YouTube Short.
Return ONLY valid JSON (no markdown backticks):
{
  "title": "Catchy YouTube Shorts title under 60 chars #shorts",
  "description": "2-sentence description with 3 hashtags",
  "scenes": [
    {"text": "Short punchy hook sentence (max 12 words)", "bg_color": "#111827"},
    {"text": "Second sentence explaining how it works (max 15 words)", "bg_color": "#1E1B4B"},
    {"text": "Third sentence with a surprising twist (max 15 words)", "bg_color": "#064E3B"},
    {"text": "Closing takeaway sentence (max 12 words)", "bg_color": "#31102F"}
  ]
}
"""
res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
data = json.loads(res.text.strip().removeprefix("```json").removesuffix("```").strip())

async def build_scenes():
    clips = []
    for i, scene in enumerate(data["scenes"]):
        mp3, png, mp4 = f"scene_{i}.mp3", f"scene_{i}.png", f"scene_{i}.mp4"
        await edge_tts.Communicate(scene["text"], "en-US-ChristopherNeural", rate="+10%").save(mp3)
        img = Image.new("RGB", (1080, 1920), color=scene["bg_color"])
        draw = ImageDraw.Draw(img)
        draw.multiline_text((540, 960), textwrap.fill(scene["text"], width=22), fill="white", font=ImageFont.load_default(size=68), anchor="mm", align="center")
        img.save(png)
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", png, "-i", mp3, "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", mp4], check=True)
        clips.append(mp4)
    return clips

clips = asyncio.run(build_scenes())
with open("concat.txt", "w") as f:
    for c in clips:
        f.write(f"file '{c}'\n")

subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy", "final_short.mp4"], check=True)

with open("final_short.mp4", "rb") as video_file:
    r = requests.post(os.environ["ZAPIER_WEBHOOK_URL"], data={"title": data["title"], "description": data["description"]}, files={"video": ("final_short.mp4", video_file, "video/mp4")})
print("Status:", r.status_code, r.text)
