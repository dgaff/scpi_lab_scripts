import time
import pyvisa
import numpy as np
import matplotlib.pyplot as plt

POWER_SUPPLY_ADDRESS = 'TCPIP::192.168.1.245::INSTR'
WAVEFORM_GENERATOR_ADDRESS = 'TCPIP::192.168.1.89::INSTR'
OSCILLOSCOPE_ADDRESS = 'TCPIP::192.168.1.235::INSTR'
DMM_ADDRESS = 'TCPIP::192.168.1.88::INSTR'

'''
    My setup. The HISLIP adapter is apparently a high-speed interface layer for VISA. I haven't used it yet.

    ('TCPIP::192.168.1.88::INSTR', 'TCPIP::192.168.1.89::INSTR', 'TCPIP::192.168.1.235::INSTR', 
    'TCPIP::192.168.1.245::INSTR', 'TCPIP::192.168.1.88::hislip0,4880::INSTR')

    (Note: S/N removed from output)

    DMM:
    Connected to TCPIP::192.168.1.88::INSTR: Keysight Technologies,34470A,   ,A.03.03-03.15-03.03-00.52-05-02

    Waveform Generator:
    Connected to TCPIP::192.168.1.89::INSTR: Agilent Technologies,33511B,    ,5.03-3.15-2.00-58-00

    Oscilloscope:
    Connected to TCPIP::192.168.1.235::INSTR: RIGOL TECHNOLOGIES,DS1104Z,    ,00.04.05.SP2

    Power Supply:
    Connected to TCPIP::192.168.1.245::INSTR: Keysight Technologies,E36234A,    ,1.0.6-1.0.3-1.01

    HISLIP Adapter for DMM:
    Connected to TCPIP::192.168.1.88::hislip0,4880::INSTR: Keysight Technologies,34470A,    ,A.03.03-03.15-03.03-00.52-05-02
'''

def list_instruments():

    rm = pyvisa.ResourceManager()

    # Scan for instruments
    print(rm.list_resources())

    for instrument in rm.list_resources():
        try:
            resource = rm.open_resource(instrument)
            print(f"Connected to {instrument}: {resource.query('*IDN?')}")
        except pyvisa.VisaIOError as e:
            print(f"Could not connect to {instrument}: {e}")
    
'''
    Helpful SCPI commands for the instruments.
'''

def sample_instrument_commands():

    rm = pyvisa.ResourceManager()

    #
    # Sample setting of voltage on the power supply
    #

    my_instrument = rm.open_resource(POWER_SUPPLY_ADDRESS)
    print(my_instrument.query('*IDN?'))

    # Set voltage to 5V on the power supply
    my_instrument.write('VOLT 5')

    # Set current limit to 1A on the power supply
    my_instrument.write('CURR 1')

    # Turn on the output of the power supply
    my_instrument.write('OUTP ON')

    # Read back the set voltage and current
    voltage = my_instrument.query('VOLT?')
    current = my_instrument.query('CURR?')
    print(f'Set Voltage: {voltage} V, Set Current: {current} A')

    # Close the instrument connection
    my_instrument.close()

    #
    # Sample setting a waveform on the waveform generator
    #

    my_instrument = rm.open_resource(WAVEFORM_GENERATOR_ADDRESS)
    print(my_instrument.query('*IDN?'))

    # Set waveform to sine, frequency to 1kHz, and amplitude to 1V, and turing the output on
    my_instrument.write('FUNC SIN')
    my_instrument.write('FREQ 2000')
    my_instrument.write('VOLT 1')
    my_instrument.write('OUTP ON')

    # Read back the waveform settings
    waveform = my_instrument.query('FUNC?')
    frequency = my_instrument.query('FREQ?')
    amplitude = my_instrument.query('VOLT?')
    print(f'Set Waveform: {waveform}, Frequency: {frequency} Hz, Amplitude: {amplitude} V')

    # Close the instrument connection
    my_instrument.close()

    #
    # Sample reading voltage from the DMM
    #

    my_instrument = rm.open_resource(DMM_ADDRESS)
    print(my_instrument.query('*IDN?'))

    # Set DMM to measure DC voltage
    my_instrument.write('CONF:VOLT:DC')
    # Read the voltage measurement
    voltage = my_instrument.query('READ?')
    print(f'Measured Voltage: {voltage} V')

    # Close the instrument connection
    my_instrument.close()

    #
    # Sample reading waveform data from the oscilloscope
    #

    my_instrument = rm.open_resource(OSCILLOSCOPE_ADDRESS)  
    print(my_instrument.query('*IDN?'))

    # # Set oscilloscope to acquire waveform data
    # my_instrument.write(':WAV:FORM ASC')
    # my_instrument.write(':WAV:DATA? CHAN1')
    # # Read the waveform data
    # waveform_data = my_instrument.query(':WAV:DATA?')
    # print(f'Waveform Data: {waveform_data}')

    # Make a Vpp measurement
    vpp = my_instrument.query(':MEASure:ITEM? VPP,CHAN1')
    print(f'Vpp Measurement: {vpp} V')

    # Close the instrument connection
    my_instrument.close()

    #
    # Uncomment the following lines to take a screenshot from the oscilloscope
    #

    # my_instrument = rm.open_resource('TCPIP::192.168.1.252::INSTR')
    # print(my_instrument.query('*IDN?'))

    # screenshot_data = my_instrument.query_binary_values(':DISP:DATA?', datatype='B', container=bytes)
    # with open('rigol_screenshot.png', 'wb') as f:
    #     f.write(screenshot_data)

    # print("Screenshot saved as rigol_screenshot.png")

    # Close the instrument connection
    # my_instrument.close()

''' 

Generate a Bode plot by sweeping frequency and measuring Vpp at each frequency. 

1. You must set the circuit and test equipment parameters in the "Circuit and test equipment setup" section.
2. You should test a few points on the frequency range manually to make sure your measurement limits are correct.

Note that the Rigol can sometimes produce weird Vpp measurements. There is retry logic in the code to help mitigate this.

'''

def bode_plot():
    rm = pyvisa.ResourceManager()
    # print(rm.list_resources()) # Note: sometimes running the script back-to-back can cause issues with the VISA resource manager, so it's good to check the resources.
    # NOTE: I wasn't closing the resource manager. Trying that to see if that fixes the issue.

    # Connect to the instruments
    dmm = rm.open_resource(DMM_ADDRESS)  # Digital Multimeter
    pwr = rm.open_resource(POWER_SUPPLY_ADDRESS)  # Power Supply
    wfg = rm.open_resource(WAVEFORM_GENERATOR_ADDRESS)  # Waveform Generator
    osc = rm.open_resource(OSCILLOSCOPE_ADDRESS)  # Oscilloscope

    # Circuit and test equipment setup
    supply_voltage = 5.0         # Set the power supply voltage
    supply_current_limit = 1.0   # Set the power supply current limit
    vpp_input = 0.01             # Input voltage peak-to-peak for the waveform generator
    start_freq = 10              # Starting frequency in Hz. Note: if you start at 1Hz, acquisition is very slow.
    end_freq = 10000000          # Ending frequency in Hz (20 MHz is the max for the 33511B)
    points_per_decade = 10       # Number of points to measure per decade
    error_check_max_gain = 1000  # Maximum gain to check for errors in the Vpp measurement
    scope_v_per_div = 0.5        # Vertical scale for the oscilloscope in V/div (500 mV/div)
    scope_trigger_level = 0.0    # Trigger level for the oscilloscope in V (0 V)

    # Turn on the function generator output
    wfg.write('FUNC SIN')
    wfg.write(f'FREQ {start_freq}')  
    wfg.write(f'VOLT {vpp_input}') 
    wfg.write('VOLT:OFFS 0')   # Set offset to 0
    wfg.write('PHAS 0')        # Set phase to 0
    wfg.write('OUTP ON')

    # Turn on the power supply
    pwr.write(f'VOLT {supply_voltage}')
    pwr.write(f'CURR {supply_current_limit}')
    pwr.write('OUTP ON')

    # Run an auto setup on the oscilloscope. This can take a while, so we set a timeout.
    # NOTE: I opted to manually set up the scope instead of using autoset since it can sometimes
    #       mess up the vertical scale and trigger settings.
    # osc.timeout = 10000
    # osc.write(':AUToscale')

    # Set the oscilloscope to AC coupling and configure the channel.
    osc.write(':CHAN1:COUP AC')  
    osc.write(f':CHAN1:SCAL {scope_v_per_div}')   
    osc.write(f':TRIGger:EDGE:LEV {scope_trigger_level}')

    # Calculate number of decades and points to collect per decade
    decades = np.log10(end_freq) - np.log10(start_freq)
    total_points = int(decades * points_per_decade)

    # Generate logarithmically spaced frequency points
    freqs = np.logspace(np.log10(start_freq), np.log10(end_freq), total_points)

    # Frequency sweep and measurement
    vpp_measurements = []
    db_measurements = []
    for freq in freqs:
        # Set the frequency on the waveform generator and wait for it to settle
        wfg.write(f'FREQ {freq}')
        print(f'Frequency: {freq:.2f} Hz, ',end='', flush=True)

        # -------------------------------------------------------------------------------------
        # Version 1: Capturing with a 200 ms delay to allow settling time
        # TODO: fix horizontal scale based on frequency - also doesn't have the retry logic
        # -------------------------------------------------------------------------------------
        # osc.write('MEAS:CLEAR')              # Clear previous measurements
        # osc.write(':RUN')                    # Start acquisition
        # time.sleep(0.2)                      # Allow measurement to settle
        # osc.write(':STOP')                   # Stop acquisition
        # vpp = float(osc.query(':MEAS:ITEM? VPP,CHAN1'))  # Read the Vpp measurement

        # -------------------------------------------------------------------------------------
        # Version 2: Taking multiple measurements and make sure they're withing 5% of each other.
        # TODO: fix horizontal scale based on frequency - retry logic below is better.
        # -------------------------------------------------------------------------------------
        # osc.write('MEAS:CLEAR')              # Clear previous measurements
        # osc.write(':RUN')                    # Start acquisition
        # time.sleep(0.2)                      # Allow measurement to settle
        # max_attempts=5                       # Number of attempts to measure Vpp
        # error_threshold = 0.05               # 5% error threshold
        # measurements = []
        # vpp = 0.0
        # for i in range(max_attempts):
        #     vpp_temp = float(osc.query(':MEAS:ITEM? VPP,CHAN1'))
        #     measurements.append(vpp_temp)
        #     if i > 0:
        #         if abs(measurements[-1] - measurements[-2]) / measurements[-2] < error_threshold: 
        #             vpp = vpp_temp
        #             break
        #         else:
        #             vpp = sum(measurements) / len(measurements) 
        #     time.sleep(0.1)
        # osc.write(':STOP')                   # Stop acquisition

        # -------------------------------------------------------------------------------------
        # Version 3: Capturing with single acquisition mode. This is the fastest.
        # -------------------------------------------------------------------------------------
        horizontal_scale = max(10/freq, 100e-6)
        osc.write(f":TIM:SCAL {horizontal_scale}")
        actual_horizontal_scale = float(osc.query(":TIM:SCAL?"))
        osc.write("ACQ:TYPE NORM")  # Normal acquisition
        osc.write("SING")           # Single acquisition
        time.sleep(0.1)             # Allow measurement to settle. This reduces bad readings.
        osc.write(':MEAS:CLEAR')    # Clear previous measurements

        # Take multiple Vpp measurements and check for validity
        max_attempts = 5
        vpp = None
        for attempt in range(max_attempts):
            while True:
                status = osc.query("TRIG:STAT?").strip()
                if status == "STOP":
                    break
                time.sleep(0.05)
            try:
                vpp_candidate = float(osc.query(':MEAS:ITEM? VPP,CHAN1'))
            except Exception:
                vpp_candidate = 0.0
            # Check for obviously erroneous values (zero, negative, or unreasonably high)
            if vpp_candidate > 0 and vpp_candidate < error_check_max_gain * vpp_input:
                vpp = vpp_candidate
                break
            else:
                print(f"Warning: Invalid Vpp measurement ({vpp_candidate}), retrying...")
                time.sleep(0.1)
                osc.write("SING")
                time.sleep(0.1)
        if vpp is None:
            print("Warning: Could not get valid Vpp measurement, setting to 0")
            vpp = 0.0

        # Store the Vpp measurement and convert to dB
        vpp_measurements.append(vpp)
        db_measurements.append(20 * np.log10(abs(vpp) / abs(vpp_input)))

        # Show the progress since this can take a while
        print(f'Horizontal Scale: {actual_horizontal_scale}, Vpp Measurement: {vpp} V')
    
    # Close the instrument connections
    dmm.close()
    pwr.close()
    wfg.close()
    osc.close()

    # Close the VISA resource manager
    rm.close()

    # Plot the Bode plot.
    plt.figure(figsize=(10, 6))
    # plt.semilogx(freqs, vpp_measurements, marker='o', linestyle='-')
    plt.semilogx(freqs, db_measurements, marker='o', linestyle='-')
    # plt.title('Bode Plot of Vpp vs Frequency')
    plt.title('Bode Plot')
    plt.xlabel('Frequency (Hz)')
    # plt.ylabel('Vpp (V)')
    plt.ylabel('dB')
    plt.grid(which='both', linestyle='--', linewidth=0.5)
    plt.xscale('log')

    # Set x-ticks at each decade (multiples of 10) with comma separators for thousands
    min_exp = int(np.floor(np.log10(freqs[0])))
    max_exp = int(np.ceil(np.log10(freqs[-1])))
    decade_ticks = [10**i for i in range(min_exp, max_exp + 1)]
    plt.xticks(decade_ticks, labels=[f'{int(x):,}' for x in decade_ticks])

    plt.tight_layout()
    plt.show()

'''
    This is just to check the frequency sweep math.
'''

def bode_plot_freq_check():
    start_freq = 10      # Starting frequency in Hz
    end_freq = 100000    # Ending frequency in Hz
    points_per_decade = 1000

    # Calculate number of decades
    decades = np.log10(end_freq) - np.log10(start_freq)
    total_points = int(decades * points_per_decade)

    # Generate logarithmically spaced frequency points
    freqs = np.logspace(np.log10(start_freq), np.log10(end_freq), total_points)

    # for freq in freqs:
    #     print(f'Frequency: {freq:.2f} Hz')

    # Calculate a histogram of the frequencies at log scale
    hist, bin_edges = np.histogram(np.log10(freqs), bins=4)

    # Plot the histogram
    plt.figure()
    plt.bar(bin_edges[:-1], hist, width=np.diff(bin_edges), edgecolor='black', align='edge')
    plt.xlabel('log10(Frequency [Hz])')
    plt.ylabel('Count')
    plt.title('Histogram of Frequencies (Log Scale)')
    plt.xticks(bin_edges, [f"{10**edge:.0f}" for edge in bin_edges], rotation=45)
    plt.tight_layout()
    plt.show()

def main():

    # list_instruments()

    # sample_instrument_commands()

    # bode_plot_freq_check()

    bode_plot()

if __name__ == "__main__":
    main()