import numpy as np
import pyvisa

WAVEFORM_GENERATOR_ADDRESS = 'TCPIP::192.168.1.89::INSTR'
CSV_FILE = 'waveform.csv'  # Update with your CSV filename
WAVEFORM_NAME = 'USER1'

'''
    NOTE: this is untested
'''

def read_waveform_csv(filename):
    # Assumes a single column of values between -1 and 1
    data = np.loadtxt(filename, delimiter=',')
    # Scale to 16-bit unsigned integer (0 to 65535)
    scaled = np.round((data + 1) * 32767.5).astype(np.uint16)
    return scaled

def upload_waveform_to_awg(waveform_data, name=WAVEFORM_NAME):
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(WAVEFORM_GENERATOR_ADDRESS)
    inst.timeout = 10000  # ms

    # Convert to comma-separated string
    data_str = ','.join(map(str, waveform_data))

    # Delete existing user waveform if needed
    inst.write(f":DATA:VOLatile:DELete '{name}'")

    # Send the waveform data
    inst.write(f":DATA:ARB:DAC {name},{data_str}")

    # Set the waveform to output
    inst.write(f":FUNCtion:ARB {name}")
    inst.write(":FUNCtion ARB")
    inst.write(":OUTPut ON")

    print(f"Waveform '{name}' uploaded and output enabled.")

def main():
    waveform = read_waveform_csv(CSV_FILE)
    upload_waveform_to_awg(waveform)

if __name__ == "__main__":
    main()