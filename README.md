# World News — Wednesday 18 November 2026

[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/maulan16/news-image-20261118/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/maulan16/news-image-20261118/reward.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)

A one-page newspaper summing up the world's news of Wednesday 18 November 2026 — drawn entirely in code, Python standard library only. Text is a smooth single-stroke vector font and the whole page is rendered at 3x and downsampled, so edges are anti-aliased instead of blocky. Panels, frames and illustration regions are large-radius rounded rectangles with soft drop shadows and gradients — nothing flat and square.

## The four stories

1. **DIPLOMACY — ASIA:** Trump lands in Manila for Quad talks, ahead of the APEC summit with Xi and Putin.
2. **WAR IN UKRAINE:** Ukraine strikes the Crimea bridge for a second day as Russia pounds bridges in Kyiv.
3. **MIDDLE EAST:** Iran drones hit a US military radar in Bahrain; Kuwait reports drone interceptions.
4. **WEATHER — INDIA:** Cyclone Akvan intensifies over the Bay of Bengal; Andhra Pradesh and Odisha on high alert.

## Run it

```
MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

This writes `out/entry.png` (1024x1024, ~117 KB). The program is fully deterministic: no clock, no network, no random — run it twice and the bytes are identical.

---

Built for the [make.fun](https://make.fun/bounty/news-image-20261118) competition **news-image-20261118**.
