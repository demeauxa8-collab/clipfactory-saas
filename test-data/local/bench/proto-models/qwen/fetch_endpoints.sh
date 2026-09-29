#!/bin/bash
mkdir -p endpoints
for m in qwen3.7-flash qwen3.5-flash-02-23 qwen3.5-9b qwen3-vl-32b-instruct qwen3-vl-8b-instruct qwen3.6-35b-a3b qwen3.5-35b-a3b qwen3-vl-30b-a3b-instruct qwen3-vl-8b-thinking qwen3.6-flash qwen3.5-27b qwen3-vl-30b-a3b-thinking qwen3-vl-235b-a22b-instruct qwen2.5-vl-72b-instruct qwen3.5-plus-02-15 qwen3.5-122b-a10b qwen3.5-plus-20260420 qwen3.7-plus qwen3.6-plus qwen3.5-397b-a17b qwen3-vl-235b-a22b-thinking qwen3.6-27b qwen3.8-max; do
  curl -s "https://openrouter.ai/api/v1/models/qwen/$m/endpoints" -o "endpoints/$m.json"
done
