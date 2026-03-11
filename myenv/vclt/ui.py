import gradio as gr

from vclt.config import CUSTOM_CSS
from vclt.ltspice import check_ltspice_installation
from vclt.parser import has_gemini_model
from vclt.workflow import (
    list_recent_circuits,
    preview_command,
    process_audio,
    process_text,
    create_circuit_from_text,
    create_circuit_from_audio,
    confirm_and_save_from_json,
)


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

                analysis_mode = gr.Radio(
                    choices=[
                        ("Transient (waveform)", "transient"),
                        ("AC (Bode plot)", "ac"),
                    ],
                    value="transient",
                    label="Simulation Mode",
                    info="Choose which analysis directive is active in the generated .asc.",
                )

                transient_stop_time = gr.Textbox(
                    value="0.2m",
                    label="Transient Stop Time",
                    lines=1,
                    info="Used when Simulation Mode is Transient. Examples: 500u, 20m, 10s",
                )

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

                        # Note: in-app analytical plots removed; run simulations in LTspice after schematic opens.

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
                parser_preview = gr.Markdown("### Parser Preview\nEnter text and click Preview Parse.")
                status_output = gr.Textbox(label="Run Status", lines=12)
                parsed_json = gr.Textbox(label="Parsed Components (edit and confirm if needed)", lines=8)
                recent_files = gr.Textbox(label="Recent Generated .asc Files", lines=8)
                with gr.Row():
                    btn_refresh = gr.Button("Refresh File List")
                    btn_clear = gr.Button("Clear")

                    confirm_button = gr.Button("Confirm & Create Circuit", variant="secondary")

                # Help/guide accordion for LTspice workflow
                with gr.Accordion("How to run and view simulations in LTspice", open=False):
                    gr.Markdown(
                        """
                        - After the schematic opens in LTspice, ensure a ground (node 0) exists.
                        - Add or confirm simulation directives (e.g. `.tran 0 0.2m` or `.ac dec 100 10 100k`).
                        - Click the Run button (running man) or press Ctrl+R to run the simulation.
                        - Click a node/wire to view voltages, or use 'Add Trace' for custom expressions.
                        - Use cursors, `.meas`, and right-click plots for measurements and FFT.
                        - Edit the schematic in LTspice and re-run; changes are saved in the .asc file.
                        """
                    )

        btn_preview.click(fn=preview_command, inputs=text_input, outputs=parser_preview)
        # Create from text: may return parsed JSON for confirmation or create and open .asc immediately
        btn_text.click(
            fn=create_circuit_from_text,
            inputs=[text_input, analysis_mode, transient_stop_time],
            outputs=[status_output, parsed_json],
        )
        btn_text.click(fn=list_recent_circuits, inputs=None, outputs=recent_files)

        # Create from audio
        btn_audio.click(
            fn=create_circuit_from_audio,
            inputs=[audio_input, analysis_mode, transient_stop_time],
            outputs=[status_output, parsed_json],
        )
        btn_audio.click(fn=list_recent_circuits, inputs=None, outputs=recent_files)

        # Confirm & save edited parsed components (JSON) -> save/open in LTspice
        confirm_button.click(
            fn=confirm_and_save_from_json,
            inputs=[parsed_json, analysis_mode, transient_stop_time],
            outputs=[status_output, recent_files],
        )

        btn_refresh.click(fn=list_recent_circuits, inputs=None, outputs=recent_files)
        btn_clear.click(
            fn=lambda: ("", "### Parser Preview\nEnter text and click Preview Parse.", "", list_recent_circuits()),
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
