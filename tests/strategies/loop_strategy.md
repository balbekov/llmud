# Loop Movement Strategy

## Overview

This is a simple strategy for testing AI-driven movement loops in DuneMUD.
The AI should perform a specific sequence of movements: north, north, south, south.

## Movement Pattern

Execute these commands in exact sequence:
1. `north` (or `n`)
2. `north` (or `n`)
3. `south` (or `s`)
4. `south` (or `s`)

Then the loop completes. After completing the loop, issue the `look` command to verify position.

## Key Commands

- Movement: n/s/e/w (north/south/east/west)
- Info: look, score

## Instructions

You are testing navigation. Your ONLY goal is to:
1. Move north twice
2. Move south twice
3. Then issue `look`

Track which step you're on based on the commands you've already issued (visible in recent output).

## Response Format

Output ONLY the single command to execute next. No explanations.

Based on how many north/south commands have been issued:
- 0 movements done → output: `n`
- 1 movement (1 north) done → output: `n`
- 2 movements (2 north) done → output: `s`
- 3 movements (2 north, 1 south) done → output: `s`
- 4 movements (loop complete) → output: `look`

## Important

- Only output the command, nothing else
- Follow the exact sequence: n, n, s, s, look
- Do not deviate from this pattern

