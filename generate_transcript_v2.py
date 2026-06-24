
import json
import os

log_file = "/home/sm/.gemini/tmp/02/chats/session-2026-05-20T04-34-970436aa.jsonl"
output_file = "project_full_transcript.md"

def get_text(data):
    m_type = data.get("type")
    content = data.get("content")
    if m_type == "user":
        if isinstance(content, list):
            return "".join([c.get("text", "") for c in content if "text" in c])
        return str(content)
    elif m_type == "gemini":
        return str(content) if content else ""
    return None

with open(log_file, "r") as f, open(output_file, "w") as out:
    out.write("# プロジェクト対話全文ログ\n\n")
    out.write("このファイルは、本プロジェクトにおけるすべての対話（プロンプトと出力）を記録したものです。\n\n---\n\n")
    
    for line in f:
        try:
            data = json.loads(line)
            m_type = data.get("type")
            text = get_text(data)
            
            if m_type == "user":
                out.write(f"### [USER] ({data.get('timestamp')})\n{text}\n\n")
            elif m_type == "gemini":
                if text.strip():
                    out.write(f"### [ASSISTANT] ({data.get('timestamp')})\n{text}\n\n")
                
                # Check for tool calls or thoughts if they exist in some structure
                # In this specific log format, it seems 'gemini' type contains the assistant response.
        except Exception as e:
            continue

print(f"Transcript written to {output_file}")
