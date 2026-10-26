import json, sys, time, urllib.request
card = open(sys.argv[1]).read()
def post(url, body, timeout=900):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"content-type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    return time.monotonic() - t0, out
# 1. large prompt: full card JSON x2 (simulating two sources + history)
msgs = [{"role": "system", "content": "Graph cards:\n" + card + "\n" + card},
        {"role": "user", "content": "Question: How do I defend against T1176? Which relation answers it? One word."}]
for i in range(2):
    dt, out = post("http://localhost:9090/v1/chat/completions",
                   {"model": "default-model", "messages": msgs, "max_tokens": 64, "temperature": 0,
                    "chat_template_kwargs": {"thinking_budget": 0, "enable_thinking": False}})
    u = out["usage"]; print(f"large prompt run{i}: {dt:.2f}s prompt={u['prompt_tokens']} completion={u['completion_tokens']} -> {out['choices'][0]['message'].get('content','')[:40]!r}")
# 2. decision model (d3-lite via GAIFA decide mod)
q = {"input": "Question: How do I defend against T1176 (Browser Extensions)?",
     "questions": [{"id": "rel", "type": "choice", "question": "Which graph relation from the technique answers the question?",
                    "options": {"MITIGATES": "a mitigation that prevents or limits the technique",
                                "DETECTS": "a detection strategy that observes the technique",
                                "USES": "a group, campaign or software that uses the technique",
                                "NONE": "none of these"}},
                   {"id": "ent", "type": "yesno", "question": "Does 'the Chrome add-on technique' refer to T1176 Browser Extensions: adversaries abuse browser extensions to establish persistent access?"}]}
for i in range(4):
    dt, out = post("http://localhost:5107/v1/decide", q)
    print(f"decide run{i}: {dt:.2f}s (server ms={out.get('ms')}) rel={out['answers']['rel'].get('top')} p={out['answers']['rel'].get('p')} ent={out['answers']['ent'].get('top')} p={out['answers']['ent'].get('p')}")
