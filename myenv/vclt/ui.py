import gradio as gr

from vclt.config import CUSTOM_CSS
from vclt.ltspice import check_ltspice_installation
from vclt.parser import has_gemini_model
from vclt.workflow import list_recent_circuits, preview_command, process_audio, process_text


def create_demo():
    with gr.Blocks(title="Voice-Controlled LTspice Circuit Creator") as demo:
        ltspice_ok, ltspice_message = check_ltspice_installation()
        parser_mode = "Gemini" if has_gemini_model() else "Rule-based fallback"

        gr.HTML(
            """
            <div class='hero'>
                <h1 style='margin:0;'>Voice-Controlled LTspice Circuit Creator</h1>
                <p style='margin:8px 0 0 0;'>Design filter circuits from speech or text, preview parsed values, then launch directly in LTspice.</p>
            </div>
            """
        )

        with gr.Row():
            with gr.Column(scale=7, elem_classes=["card"]):
                gr.Markdown(f"**Parser Mode:** `{parser_mode}`")
                if not ltspice_ok:
                    gr.Markdown(f"**LTspice Check:** `{ltspice_message}`")

                with gr.Tabs():
                    with gr.Tab("Voice Input"):
                        audio_input = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            label="Record Voice Command",
                        )
                        btn_audio = gr.Button("Create Circuit from Audio", variant="primary")

                    with gr.Tab("Text Input"):
                        text_input = gr.Textbox(
                            label="Type Circuit Description",
                            lines=3,
                            placeholder="Example: RC low pass filter with 10k resistor and 1uF capacitor at 25 kilohertz",
                        )
                        with gr.Row():
                            btn_preview = gr.Button("Preview Parse")
                            btn_text = gr.Button("Create Circuit from Text", variant="primary")

                gr.Examples(
                    examples=[
                        ["simple circuit with 5V, 1 ohm resistor and 2 uF capacitor"],
                        ["RC low pass filter with 10k resistor and 1 microfarad capacitor at 25 kilohertz"],
                        ["RC high pass filter with 4.7k resistor and 100 nanofarad capacitor at 5 kilohertz"],
                        ["RC band pass filter with 1k resistors and 100 nanofarad capacitors at 10 kilohertz"],
                    ],
                    inputs=[text_input],
                    label="Quick Examples",
                )

            with gr.Column(scale=5, elem_classes=["card"]):
                parser_preview = gr.Markdown("### Parser Preview\\nEnter text and click Preview Parse.")
                status_output = gr.Textbox(label="Run Status", lines=12)
                recent_files = gr.Textbox(label="Recent Generated .asc Files", lines=8)
                with gr.Row():
                    btn_refresh = gr.Button("Refresh File List")
                    btn_clear = gr.Button("Clear")

        btn_preview.click(fn=preview_command, inputs=text_input, outputs=parser_preview)
        btn_text.click(fn=process_text, inputs=text_input, outputs=status_output)
        btn_text.click(fn=preview_command, inputs=text_input, outputs=parser_preview)
        btn_text.click(fn=list_recent_circuits, inputs=None, outputs=recent_files)

        btn_audio.click(fn=process_audio, inputs=audio_input, outputs=status_output)
        btn_audio.click(fn=list_recent_circuits, inputs=None, outputs=recent_files)

        btn_refresh.click(fn=list_recent_circuits, inputs=None, outputs=recent_files)
        btn_clear.click(
            fn=lambda: ("", "### Parser Preview\\nEnter text and click Preview Parse.", "", list_recent_circuits()),
            inputs=None,
            outputs=[text_input, parser_preview, status_output, recent_files],
        )

        demo.load(fn=list_recent_circuits, inputs=None, outputs=recent_files)

    return demo


def launch_app():
    demo = create_demo()
    demo.launch(
        theme=gr.themes.Soft(primary_hue="amber", secondary_hue="sky", neutral_hue="slate"),
        css=CUSTOM_CSS,
    )
