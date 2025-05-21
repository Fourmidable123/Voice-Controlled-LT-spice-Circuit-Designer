# Voice Controlled LT-spice Circuit Designer

## Date Created - 2nd April, 2025

## Introduction
- Designing circuits in LTspice requires manual schematic entry, which can be slow and complex for beginners. This project simplifies the process using voice commands—just describe your circuit (e.g., "1k resistor and 10uF capacitor"), and the system automatically generates the LTspice schematic.
- By combining speech recognition (Google Speech-to-Text) and AI parsing (Gemini), the tool eliminates manual netlist writing, making circuit simulation faster and more intuitive. The generated design opens directly in LTspice for instant testing.
- Perfect for students and engineers, this project bridges voice control and circuit simulation, reducing errors and speeding up prototyping.

## Problem Statement
Traditional circuit design using simulation tools like LTspice requires manual input of components and parameters, which can be:

- Time-consuming for simple circuits
- Error-prone when entering component values
- Inaccessible for users with limited technical expertise
- Cumbersome for rapid prototyping

There's a need for an intuitive interface that allows users to design circuits through natural language commands, reducing the learning curve and improving design efficiency.

## Research Gap Summary
![image](https://github.com/user-attachments/assets/43555aef-9797-4c04-bd11-954cebdde237)

## Methodology
- Voice Input: User speaks circuit description.
- Speech Recognition: Google API converts speech to text.
- AI Parsing: Gemini extracts components (e.g., "1kΩ → 1000").
- Schematic Generation: Python auto-generates .asc file.
- LT-spice Integration: Circuit opens for simulation.
- GUI: Gradio interface for user interaction.
![image](https://github.com/user-attachments/assets/9f96673e-634d-4f71-8099-0b2c0498eaa6)

## Conclusion
- This project bridges the gap between natural language interaction and circuit simulation, making LTspice more accessible and efficient.
- By combining speech recognition, AI parsing, and automated schematic generation, it provides a hands-free, intuitive way to design and simulate circuits. Future enhancements could include:
- Support for more complex circuits (op-amps, transistors).
- Error correction in voice commands.
- Integration with other simulation tools (e.g., MATLAB, Simulink).
- Multi-language support for global accessibility.
