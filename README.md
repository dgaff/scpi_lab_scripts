# SCPI Scripts and Tools

This repo is for various instrument control scripts for my SCPI-compatible electronics lab equipment. SCPI stands for [Standard Commands for Programmable Instruments](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments). It's pronounced "skippy" apparently, and it goes back to 1990. Back when I was at Virginia Tech in the early 90s, I was responsible for maintaining and enhancing the lab software that controlled the instruments in the electronics lab. I suspect it was SCPI back then too, but the physical interface was GPIB/HP-IB, which was a thick parallel cable with many pins. Now we get to use Ethernet, thankfully.

![](images/scpi_lab_equipment.jpeg)

Current equipment list supported:

    DMM: Keysight 34470A

    Waveform Generator: Agilent (Keysight) 33511B

    Oscilloscope: RIGOL DS1104Z

    Power Supply: Keysight E36234A

## Bode Plots

capture.py produces a Bode Plot. Here's an example of a Common Emitter BJT amplifier circuit and it's Bode Plot.

![](images/actual_circuit.png)

![](images/actual_bode.png)

## Waveform Generation

waveform_generator.py allows you to generate a variaty of waveforms, including drawing an arbitrary one. It's still a work in progress.

arb_waveform.py uploads a waveform to the waveform generator. It's currently untested.

![](images/arb_waveform.png)