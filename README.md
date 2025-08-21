# Bode Plot and other useful SCPI scripts

This repo is for various instrument control scripts for my SCPI-compatible electronics lab equipment. SCPI stands for [Standard Commands for Programmable Instruments](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments). It's pronounced "skippy" apparently, and it goes back to 1990. Back when I was at Virginia Tech, I was responsible for maintaining and enhancing the lab software that controlled the instruments in the electronics lab. The interface back then was GPIB, which was a thick cable with many pins. Now we get to use Ethernet, thankfully.

![](images/scpi_lab_equipment.jpeg)

Current equipment list supported:

    DMM: Keysight 34470A

    Waveform Generator: Agilent (Keysight) 33511B

    Oscilloscope: RIGOL DS1104Z

    Power Supply: Keysight E36234A

There are some instrument detection and test functions included. But the primary function is to produce Bode Plots. Here's an example of a Common Emitter BJT amplifier circuit and it's Bode Plot.

![](images/actual_circuit.png)

![](images/actual_bode.png)