#!/usr/bin/env python3
"""Generate scene TTS files and assemble a measured voiceover timeline."""

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts


async def generate_scene(scene: dict, voice: str, output_dir: Path) -> Path:
    target = output_dir / f"{scene['id']}.mp3"
    communicate = edge_tts.Communicate(
        scene["text"],
        voice,
        rate=scene.get("rate", "+0%"),
    )
    await communicate.save(str(target))
    return target


async def run(args) -> None:
    manifest_path = Path(args.manifest).resolve()
    scenes = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not scenes:
        raise ValueError("Narration manifest is empty")

    output_dir = Path(args.output_dir).resolve()
    scene_dir = output_dir / "voice-native"
    scene_dir.mkdir(parents=True, exist_ok=True)
    files = await asyncio.gather(*(generate_scene(scene, args.voice, scene_dir) for scene in scenes))

    command = ["ffmpeg", "-y"]
    for file in files:
        command.extend(["-i", str(file)])

    filters = []
    labels = []
    for index, scene in enumerate(scenes):
        delay = round(float(scene["start"]) * 1000)
        label = f"v{index}"
        filters.append(
            f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"adelay={delay}|{delay}[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels)
        + f"amix=inputs={len(scenes)}:duration=longest:normalize=0,"
        + f"apad=whole_dur={args.duration},atrim=0:{args.duration},"
        + "loudnorm=I=-16:TP=-1.5:LRA=7[voice]"
    )

    output = output_dir / "voiceover.wav"
    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[voice]",
        "-ar", "48000",
        "-ac", "2",
        "-c:a", "pcm_s16le",
        "-t", str(args.duration),
        str(output),
    ])
    subprocess.run(command, check=True)
    print(f"Created {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--output-dir", default="audio")
    parser.add_argument("--voice", default="en-US-AriaNeural")
    parser.add_argument("--duration", type=float, default=60.0)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
