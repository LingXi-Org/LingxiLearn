---
name: chinese-greeting
description: >-
  Create a short, friendly greeting or welcome message in Simplified Chinese while preserving the
  user's requested tone and situation. Use when the user asks for a greeting, welcome, opening,
  or brief Chinese salutation. Chinese display name: 中文问候生成。Chinese display description:
  生成简短、友好、符合语气的中文问候语或欢迎语。
license: MIT
compatibility: LingxiGraph Agent Skills runtime
metadata:
  author: LingXi-Org
  version: 1.0.0
  display-name: 中文问候生成
  display-description: 生成简短、友好、符合语气的中文问候语或欢迎语。
  output-language: zh-CN
  output-contract: chinese-greeting-result.v1
  execution-mode: synchronous
---

# Chinese Greeting

## Role

Create one short, friendly greeting in Simplified Chinese. Match the requested tone, audience,
occasion, and formality. If the user does not specify a tone, use warm and concise wording.

## Output language

Return Chinese prose only. Preserve names, product names, code identifiers, URLs, and other proper
nouns exactly when needed. Do not switch to another natural language merely because the input is in
another language; this skill's contract is Chinese output.

## Procedure

1. Identify the occasion, audience, tone, and any required name.
2. Read `references/greetings.md` only when a localized Chinese example is useful.
3. Use `assets/greeting-template.txt` when the user asks for a reusable template.
4. Keep the result concise unless the user requests variants or a longer welcome.

The bundled `scripts/chinese_greeting.py` is an optional readable example. Reading this skill never authorizes
or executes it, and you must not claim to have run it without an independently authorized tool.
