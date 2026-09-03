#!/usr/bin/env python3
"""Render a seekable HTML animation to a deterministic H.264 MP4."""

import argparse
import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright


async def wait_frames(page, count: int) -> None:
    await page.evaluate(
        """count => new Promise(resolve => {
            let seen = 0;
            const step = () => (++seen >= count) ? resolve() : requestAnimationFrame(step);
            requestAnimationFrame(step);
        })""",
        count,
    )


async def capture_bucket(context, url: str, frames: list[int], args, temp_dir: Path) -> None:
    page = await context.new_page()
    await page.goto(url, wait_until="load", timeout=60_000)
    await page.wait_for_function(
        "window.__ready === true && typeof window.__seek === 'function'",
        timeout=args.ready_timeout * 1000,
    )

    for frame in frames:
        await page.evaluate("t => window.__seek(t)", frame / args.fps)
        await wait_frames(page, args.settle)
        await page.screenshot(
            path=str(temp_dir / f"frame-{frame:06d}.png"),
            clip={"x": 0, "y": 0, "width": args.width, "height": args.height},
        )
    await page.close()


async def render(args) -> None:
    html = Path(args.html).resolve()
    if not html.exists():
        raise FileNotFoundError(html)
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is not available on PATH")

    output = Path(args.output).resolve() if args.output else html.with_name(f"{html.stem}-silent.mp4")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="stickman-frames-", dir=output.parent))
    total_frames = round(args.duration * args.fps)
    buckets = [[] for _ in range(args.workers)]
    for frame in range(total_frames):
        buckets[frame % args.workers].append(frame)

    print(f"Rendering {total_frames} frames at {args.width}x{args.height}, {args.fps} FPS")
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            context = await browser.new_context(
                viewport={"width": args.width, "height": args.height},
                device_scale_factor=1,
            )
            await context.add_init_script(
                "window.__recording = true; window.__seekRender = true;"
            )
            await asyncio.gather(
                *(capture_bucket(context, html.as_uri(), bucket, args, temp_dir) for bucket in buckets if bucket)
            )
            await browser.close()

        captured = len(list(temp_dir.glob("frame-*.png")))
        if captured != total_frames:
            raise RuntimeError(f"Expected {total_frames} frames, captured {captured}")

        command = [
            "ffmpeg", "-y",
            "-framerate", str(args.fps),
            "-i", str(temp_dir / "frame-%06d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(args.crf),
            "-preset", args.preset,
            "-r", str(args.fps),
            "-movflags", "+faststart",
            str(output),
        ]
        subprocess.run(command, check=True)
        print(f"Created {output}")
    finally:
        if args.keep_frames:
            print(f"Kept frames in {temp_dir}")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html")
    parser.add_argument("--output")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--settle", type=int, default=2)
    parser.add_argument("--ready-timeout", type=int, default=10)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--keep-frames", action="store_true")
    args = parser.parse_args()
    args.workers = max(1, args.workers)
    args.settle = max(1, args.settle)
    asyncio.run(render(args))


if __name__ == "__main__":
    main()
