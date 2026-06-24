
import json

log_file = "/home/sm/.gemini/tmp/02/chats/session-2026-05-20T04-34-970436aa.jsonl"
output_file = "project_full_transcript.md"

with open(log_file, "r") as f, open(output_file, "w") as out:
    out.write("# プロジェクト対話全文ログ\n\n")
    for line in f:
        try:
            data = json.loads(line)
            m_type = data.get("type")
            if m_type == "user":
                content = data.get("content", [])
                text = "".join([c.get("text", "") for c in content if "text" in c])
                out.write(f"### [USER] ({data.get('timestamp')})\n{text}\n\n")
            elif m_type == "model":  # Usually assistant is 'model' in Gemini logs
                content = data.get("content", [])
                text = "".join([c.get("text", "") for c in content if "text" in c])
                if text.strip():
                    out.write(f"### [ASSISTANT] ({data.get('timestamp')})\n{text}\n\n")
            elif m_type == "call": # Tool call
                # You can include tool calls if needed
                pass
            elif m_type == "response": # Tool response
                # You can include tool responses if needed
                pass
        except:
            continue

print(f"Transcript written to {output_file}")
