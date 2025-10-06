import time
import pyvisa
import numpy as np
import matplotlib.pyplot as plt

POWER_SUPPLY_ADDRESS = 'TCPIP::192.168.1.122::INSTR'
# POWER_SUPPLY_ADDRESS = 'TCPIP::192.168.1.122::5025::SOCKET'
WAVEFORM_GENERATOR_ADDRESS = 'TCPIP::192.168.1.227::INSTR'
RIGOL_OSCILLOSCOPE_ADDRESS = 'TCPIP::192.168.1.226::INSTR'
SIGLENT_OSCILLOSCOPE_ADDRESS = 'TCPIP::192.168.1.22::INSTR'
# SIGLENT_OSCILLOSCOPE_ADDRESS = 'TCPIP::192.168.1.22::5025::SOCKET'
DMM_ADDRESS = 'TCPIP::192.168.1.248::INSTR'

'''
    My setup. The HISLIP adapter is apparently a high-speed interface layer for VISA. I haven't used it yet.
    (Note: S/N removed from output)

    ('TCPIP::192.168.1.22::INSTR', 'TCPIP::192.168.1.122::INSTR', 'TCPIP::192.168.1.226::INSTR', 
    'TCPIP::192.168.1.227::INSTR', 'TCPIP::192.168.1.248::INSTR', 'TCPIP::192.168.1.248::hislip0,4880::INSTR')
    
    Siglent Scope:
    Connected to TCPIP::192.168.1.22::INSTR: Siglent Technologies,SDS3054X HD,  ,4.8.9.1.0.3.9

    Power Supply:
    Connected to TCPIP::192.168.1.122::INSTR: Keysight Technologies,E36234A,  ,1.0.6-1.0.3-1.01

    Rigol Scope:
    Connected to TCPIP::192.168.1.226::INSTR: RIGOL TECHNOLOGIES,DS1104Z,  ,00.04.05.SP2

    Waveform Generator:
    Connected to TCPIP::192.168.1.227::INSTR: Agilent Technologies,33511B,  ,5.03-3.15-2.00-58-00

    DMM:
    Connected to TCPIP::192.168.1.248::INSTR: Keysight Technologies,34470A,  ,A.03.03-03.15-03.03-00.52-05-02

    HISLIP Adapter for DMM:
    Connected to TCPIP::192.168.1.248::hislip0,4880::INSTR: Keysight Technologies,34470A,  ,A.03.03-03.15-03.03-00.52-05-02
    
'''

def list_instruments():
    '''
    This function lists all connected instruments and attempts to connect to them using two different VISA backends.

    When I upgraded to macOS Tahoe, the py VISA backend stopped connecting correctly to some devices. I had to install 
    the NI-VISA library and use that backend to connect to the devices. However, the NI-VISA backend doesn't correctly 
    enumerate the devices, so I use the py backend to list the devices and then connect to them using the NI-VISA backend. 
    The NI-VISA backend is also a couple of years old now, which is a bit concerning. The last update adapted the backend
    to Apple Silicon. I think there are bugs in both py and ni backends with enumeration, but this works for now.

    Some devices also support the direct SOCKET connection, but it's not advertised by the py backend or the NI-VISA backend.
    A socket connection looks like this: 'TCPIP0::192.168.1.122::5025::SOCKET' There's some code to extract the IPs in case
    I want to use a socket connection.

    Finally, the list_resources() function will also list local serial and USB devices, regardless of whether they are
    actually instruments. So those are filtered out by looking for 'INSTR' in the resource string.
    '''
    
    rm_py = pyvisa.ResourceManager('@py')
    print(rm_py.list_resources('TCPIP?'))

    # This code is for trying SOCKET connections.
    # ips = []
    # for r in rm_py.list_resources('TCPIP?*::INSTR'):
    #     ips.append(r.split('::')[1])
    # print("Found IPs:", ips)

    # The NI-VISA backend is called "ivi" rather than "ni" on macOS for some reason. It can also be referenced directly.
    # rm_ni = pyvisa.ResourceManager('/Library/Frameworks/VISA.framework/VISA')
    rm_ni = pyvisa.ResourceManager('@ivi')

    for instrument in rm_py.list_resources('TCPIP?'):
        try:
            resource = rm_ni.open_resource(instrument)
            print(f"Connected to {instrument}: {resource.query('*IDN?')}")
        except pyvisa.VisaIOError as e:
            print(f"Could not connect to {instrument}: {e}")

    # This code is for trying SOCKET connections.
    # for ip in ips:
    #     rsrc = f'TCPIP0::{ip}::5025::SOCKET'
    #     inst = rm_ni.open_resource(rsrc)
    #     inst.write_termination = '\n'; inst.read_termination = '\n'
    #     print(inst.query('*IDN?').strip())

    # This code is for checking the various types of VISA connections.
    # rm = pyvisa.ResourceManager('/Library/Frameworks/VISA.framework/VISA')
    # print("VISA lib:", rm.visalib)
    # print("GEN  :", rm.list_resources('?*'))
    # print("INSTR:", rm.list_resources('TCPIP?*::INSTR'))
    # print("SOCK :", rm.list_resources('TCPIP*::5025::SOCKET'))   # pattern with port
    # print("SOCK2:", rm.list_resources('TCPIP?*::SOCKET'))

    # This code is required when using the SOCKET connection, but not with the INSTR connection.
    # resource = rm.open_resource(POWER_SUPPLY_ADDRESS)
    # resource.read_termination = '\n'
    # resource.write_termination = '\n'
    # resource.timeout = 5000
    
'''
    Helpful SCPI commands for the instruments.
'''

def sample_siglent_commands():

    rm = pyvisa.ResourceManager('@ivi')

    my_instrument = rm.open_resource(SIGLENT_OSCILLOSCOPE_ADDRESS)
    # my_instrument.timeout = 5000
    print(my_instrument.query('*IDN?'))
    print(my_instrument.query('C1:PAVA? PKPK'))
    my_instrument.write('C1:CPL A1M')
    my_instrument.write('C1:VDIV 0.5V')
    my_instrument.write('C1:TRIG_LEVEL 0.0V')
    vpp = my_instrument.query('C1:PAVA? PKPK')
    print(f'Vpp Measurement: {vpp} V')

def sample_instrument_commands():

    rm = pyvisa.ResourceManager('@ivi')

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
    # Sample reading waveform data from the Rigol oscilloscope
    #

    my_instrument = rm.open_resource(RIGOL_OSCILLOSCOPE_ADDRESS)  
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

I have code for Rigol and Siglent scopes here. Note that I'm _not_ using Siglent's Tek compatibility mode.

'''

def bode_plot():
    rm = pyvisa.ResourceManager()
    # print(rm.list_resources()) # Note: sometimes running the script back-to-back can cause issues with the VISA resource manager, so it's good to check the resources.
    # NOTE: I wasn't closing the resource manager. Trying that to see if that fixes the issue.

    # Connect to the instruments
    # dmm = rm.open_resource(DMM_ADDRESS)  # Digital Multimeter
    pwr = rm.open_resource(POWER_SUPPLY_ADDRESS)  # Power Supply
    wfg = rm.open_resource(WAVEFORM_GENERATOR_ADDRESS)  # Waveform Generator
    # osc = rm.open_resource(RIGOL_OSCILLOSCOPE_ADDRESS)  # Rigol Oscilloscope
    osc = rm.open_resource(SIGLENT_OSCILLOSCOPE_ADDRESS)  # Siglent Oscilloscope

    # Circuit and test equipment setup
    supply_voltage = 5.0         # Set the power supply voltage
    supply_current_limit = 1.0   # Set the power supply current limit
    vpp_input = 0.01             # Input voltage peak-to-peak for the waveform generator
    start_freq = 10              # Starting frequency in Hz. Note: if you start at 1Hz, acquisition is very slow.
    end_freq = 10000000          # Ending frequency in Hz (20 MHz is the max for the 33511B. 30Mhz with SW upgrade.)
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

    # RIGOL: Set the oscilloscope to AC coupling and configure the channel.
    # osc.write(':CHAN1:COUP AC')  
    # osc.write(f':CHAN1:SCAL {scope_v_per_div}')   
    # osc.write(f':TRIGger:EDGE:LEV {scope_trigger_level}')

    # SIGLENT: Set the oscilloscope to AC coupling and configure the channel.
    osc.write('C1:CPL A1M')  
    osc.write(f'C1:VDIV {scope_v_per_div}V')   
    osc.write(f'C1:TRIG_LEVEL {scope_trigger_level}V')

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
        # RIGOL. Not modified for Siglent.
        # Version 1: Capturing with a 200 ms delay to allow settling time
        # TODO: fix horizontal scale based on frequency - also doesn't have the retry logic
        # -------------------------------------------------------------------------------------
        # osc.write('MEAS:CLEAR')              # Clear previous measurements
        # osc.write(':RUN')                    # Start acquisition
        # time.sleep(0.2)                      # Allow measurement to settle
        # osc.write(':STOP')                   # Stop acquisition
        # vpp = float(osc.query(':MEAS:ITEM? VPP,CHAN1'))  # Read the Vpp measurement

        # -------------------------------------------------------------------------------------
        # RIGOL. Not modified for Siglent.
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

        # RIGOL: Set horizontal scale
        # osc.write(f":TIM:SCAL {horizontal_scale}")
        # actual_horizontal_scale = float(osc.query(":TIM:SCAL?"))
        # osc.write("ACQ:TYPE NORM")  # Normal acquisition
        # osc.write("SING")           # Single acquisition
        # time.sleep(0.1)             # Allow measurement to settle. This reduces bad readings.
        # osc.write(':MEAS:CLEAR')    # Clear previous measurements

        # Siglent: Set horizontal scale
        osc.write(f"TDIV {horizontal_scale}")
        tdiv_response = osc.query("TDIV?")
        tdiv_response = tdiv_response.strip() # Remove /n from end
        actual_horizontal_scale = float(tdiv_response.rstrip('S'))  # Remove 'S' and convert to float
        osc.write("ACQW SAMPLING")  # Normal acquisition
        osc.write("ARM")            # Single acquisition
        time.sleep(0.1)             # Allow measurement to settle. This reduces bad readings.
        osc.write('PARAMETER_CLR')  # Clear previous measurements

        # RIGOL:Take multiple Vpp measurements and check for validity
        # max_attempts = 5
        # vpp = None
        # for attempt in range(max_attempts):
        #     while True:
        #         status = osc.query("TRIG:STAT?").strip()
        #         if status == "STOP":
        #             break
        #         time.sleep(0.05)
        #     try:
        #         vpp_candidate = float(osc.query(':MEAS:ITEM? VPP,CHAN1'))
        #     except Exception:
        #         vpp_candidate = 0.0
        #     # Check for obviously erroneous values (zero, negative, or unreasonably high)
        #     if vpp_candidate > 0 and vpp_candidate < error_check_max_gain * vpp_input:
        #         vpp = vpp_candidate
        #         break
        #     else:
        #         print(f"Warning: Invalid Vpp measurement ({vpp_candidate}), retrying...")
        #         time.sleep(0.1)
        #         osc.write("SING")
        #         time.sleep(0.1)
        # if vpp is None:
        #     print("Warning: Could not get valid Vpp measurement, setting to 0")
        #     vpp = 0.0

        # Siglent: Take multiple Vpp measurements and check for validity
        max_attempts = 5
        vpp = None
        for attempt in range(max_attempts):
            while True:
                status = osc.query("TRIG:STAT?").strip()
                if status == "Stop":
                    break
                time.sleep(0.05)
            try:
                # String format looks like this: 'C1:PAVA PKPK,2.34E+00V\n'
                pkpk_str = osc.query('C1:PAVA? PKPK')
                pkpk_str = pkpk_str.strip()  # Remove \n
                vpp_candidate = float(pkpk_str.split(',')[1].rstrip('V'))  # Remove 'V' and convert to float
            except Exception:
                print("Exception reading Vpp")
                vpp_candidate = 0.0
            # Check for obviously erroneous values (zero, negative, or unreasonably high)
            if vpp_candidate > 0 and vpp_candidate < error_check_max_gain * vpp_input:
                vpp = vpp_candidate
                break
            else:
                print(f"Warning: Invalid Vpp measurement ({vpp_candidate}), retrying...")
                time.sleep(0.1)
                osc.write("ARM")
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
    # dmm.close()
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

    # sample_siglent_commands()

    # bode_plot_freq_check()

    bode_plot()

if __name__ == "__main__":
    main()