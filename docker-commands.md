# Docker Model Runner Commands

## From Host Terminal

```bash
curl --location 'http://localhost:12434/engines/v1/chat/completions' \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "ai/qwen3:0.6B-Q4_0",
    "messages": [
      {"role": "user", "content": "Hello, Qwen3!"}
    ]
  }'

  ## From within the container

  curl  'http://host.docker.internal:12434/engines/v1' \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ai/gemma3",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant."
      },
      {
        "role": "user",
        "content": "Please write 50 words about the fall of Rome."
      }
    ]
  }'