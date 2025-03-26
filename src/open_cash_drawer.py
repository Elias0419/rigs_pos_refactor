import serial
import time
import logging
logger = logging.getLogger('rigs_pos')

def open_cash_drawer(port="/dev/ttyUSB0", baudrate=9600):
    try:
        with serial.Serial(port, baudrate) as ser:
            ser.write(b"\x00")
            time.sleep(0.1)
    except serial.SerialException as e:
        logger.warn("[open_cash_drawer]",e)

if __name__ == "__main__":
    open_cash_drawer()
