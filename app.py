"""Chat demo (Gradio).  Run:  python app.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import gradio as gr

from shiftright.answer import DISCLAIMER, answer_question
from shiftright.cli import INDEX_PATH, load_index
from shiftright.llm import get_llm
from shiftright.sources import ATTRIBUTION, LICENCE_NAME, LICENCE_URL

EXAMPLES = [
    "Do casual employees get paid more per hour?",
    "Is an unpaid trial shift legal?",
    "How much annual leave do full-time employees get?",
    "My boss hasn't given me a payslip. Is that allowed?",
    "What happens to my unused annual leave when I resign?",
]

index = load_index() if INDEX_PATH.exists() else None
llm = get_llm()


def respond(message, history):
    if index is None:
        return "The search index isn't built yet. Run `python -m shiftright.cli ingest` first."
    try:
        ans = answer_question(message, index, llm)
    except Exception as exc:  # noqa: BLE001
        return f"The language model didn't respond ({exc}). Is Ollama running? Try `ollama serve`."
    if not ans.covered:
        return ans.text
    links = "\n".join(f"{s.number}. [{s.title} › {s.heading}]({s.url})" for s in ans.sources)
    return f"{ans.text}\n\n**Sources**\n{links}\n\n_{DISCLAIMER}_"


with gr.Blocks(title="ShiftRight") as demo:
    gr.Markdown(
        "# ShiftRight\nAsk about pay, casual work, leave, rosters, unpaid trials or ending a job in Australia. "
        "Every answer cites the official guidance page it came from."
    )
    gr.ChatInterface(respond, examples=EXAMPLES)
    gr.Markdown(
        f"<small>Answers draw on guidance pages {ATTRIBUTION}, used under the "
        f"[{LICENCE_NAME}]({LICENCE_URL}) licence. Text is split into passages for search. "
        "ShiftRight is a student project and is not affiliated with or endorsed by the Fair Work Ombudsman. "
        f"Model: {llm.name}.</small>"
    )

if __name__ == "__main__":
    demo.launch()
