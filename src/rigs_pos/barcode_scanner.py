import threading
import usb
import usb.core
import usb.util
import re
import subprocess
import time

import logging
logger = logging.getLogger('rigs_pos')

class BarcodeScanner:
    def __init__(self, ref):
        self.app = ref
        self.current_barcode = ""
        # work
        self.idVendor = 0x05E0
        self.idProduct = 0x1200
        # home
        # self.idVendor = 0x28e9
        # self.idProduct = 0x03da
        try:
            self.device = self.initializeUSBDevice()
        except ValueError as e:
            logger.warn(e)  # TODO do something

        self.barcode_ready = threading.Event()
        self.stop_thread = threading.Event()
        self.thread = threading.Thread(target=self.capture_raw_data, daemon=True)
        self.thread.start()

    def initializeUSBDevice(self):

        device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if device is None:
            raise ValueError("[Barcode Scanner]: Device Not Found")
        try:
            if device.is_kernel_driver_active(0):
                device.detach_kernel_driver(0)
        except Exception as e:
            logger.warn(f"[Barcode Scanner] detach_kernel_driver fail\n{e}")
        try:
            device.set_configuration()
        except Exception as e:
            logger.warn(f"[Barcode Scanner] set_configuration fail\n{e}")
        try:
            configuration = device.get_active_configuration()
        except Exception as e:
            logger.warn(f"[Barcode Scanner] get_active_configuration fail\n{e}")

        interface = configuration[(0, 0)]
        try:
            self.endpoint = usb.util.find_descriptor(
                interface,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                == usb.util.ENDPOINT_IN,
            )
        except Exception as e:
            logger.warn(f"[Barcode Scanner] set endpoint fail\n{e}")

        return device

    def capture_raw_data(self):

        conversion_table = {
            0: ["", ""],
            4: ["a", "A"],
            5: ["b", "B"],
            6: ["c", "C"],
            7: ["d", "D"],
            8: ["e", "E"],
            9: ["f", "F"],
            10: ["g", "G"],
            11: ["h", "H"],
            12: ["i", "I"],
            13: ["j", "J"],
            14: ["k", "K"],
            15: ["l", "L"],
            16: ["m", "M"],
            17: ["n", "N"],
            18: ["o", "O"],
            19: ["p", "P"],
            20: ["q", "Q"],
            21: ["r", "R"],
            22: ["s", "S"],
            23: ["t", "T"],
            24: ["u", "U"],
            25: ["v", "V"],
            26: ["w", "W"],
            27: ["x", "X"],
            28: ["y", "Y"],
            29: ["z", "Z"],
            30: ["1", "!"],
            31: ["2", "@"],
            32: ["3", "#"],
            33: ["4", "$"],
            34: ["5", "%"],
            35: ["6", "^"],
            36: ["7", "&"],
            37: ["8", "*"],
            38: ["9", "("],
            39: ["0", ")"],
            40: ["\n", "\n"],
            41: ["\x1b", "\x1b"],
            42: ["\b", "\b"],
            43: ["\t", "\t"],
            44: [" ", " "],
            45: ["-", "-"],
            46: ["=", "+"],
            47: ["[", "{"],
            48: ["]", "}"],
            49: ["\\", "|"],
            50: ["#", "~"],
            51: [";", ":"],
            52: ["'", '"'],
            53: ["`", "~"],
            54: [",", "<"],
            55: [".", ">"],
            56: ["/", "?"],
            100: ["\\", "|"],
            103: ["=", "="],
        }

        while not self.stop_thread.is_set():
            try:
                data = self.device.read(
                    self.endpoint.bEndpointAddress,
                    self.endpoint.wMaxPacketSize,
                    timeout=5000,
                )
                # print(f"Raw USB data: {data}")
                if data[2] != 0:
                    character = conversion_table.get(data[2], [""])[0]
                    if character == "\n":
                        try:
                            # barcode scans don't reset the inactivity timer
                            # so we try to send a keypress on scan to prevent the
                            # screen from sleeping during scanning
                            subprocess.run(["xdotool", "key", "Shift_L"])
                        except FileNotFoundError as e:
                            logger.info("[BarcodeScanner]: Expected error when xdotool is unavailable\n",e)
                        except Exception as e:
                            logger.warn("[BarcodeScanner]: Unexpected error in capture_raw_data\n",e)
                        # print(f"Barcode detected: {self.current_barcode}")
                        self.barcode_ready.set()

                    else:
                        self.current_barcode += character
            except AttributeError as e:
                logger.warn(e)
                break
            except usb.core.USBError as e:
                if e.errno == 110:
                    continue

                else:
                    raise

    def is_barcode_ready(self):
        return self.barcode_ready.is_set()

    def check_for_scanned_barcode(self, dt):
        if self.is_barcode_ready():
            barcode = self.current_barcode
            self.handle_global_barcode_scan(barcode)
            self.current_barcode = ""
            self.barcode_ready.clear()

    def handle_global_barcode_scan(self, barcode):

        if self.app.current_context == "inventory":
            self.app.inventory_manager.handle_scanned_barcode(barcode)
        elif self.app.current_context == "label":
            self.app.label_manager.handle_scanned_barcode(barcode)
        elif self.app.current_context == "inventory_item":
            self.app.inventory_manager.handle_scanned_barcode_item(barcode)

        else:
            self.handle_scanned_barcode(barcode)

    def handle_scanned_barcode(self, barcode):
        # try:
            if "-" in barcode and any(c.isalpha() for c in barcode):
                self.app.history_manager.display_order_details_from_barcode_scan(
                    barcode
                )
                return

            known_barcodes = self.app.barcode_cache.keys()

            if barcode in known_barcodes:
                self.handle_known_barcode(barcode)
                return

            for known_barcode in known_barcodes:
                if (
                    known_barcode[1:] == barcode
                    or known_barcode == barcode[:-4]
                    or known_barcode[1:] == barcode[:-4]
                ):
                    self.handle_known_barcode(known_barcode)
                    return

            self.app.popup_manager.show_add_or_bypass_popup(barcode)

        # except Exception as e:
        #     print(f"Exception in handle_scanned_barcode\n{e}")

    def handle_known_barcode(self, known_barcode):
        barcode_data = self.app.barcode_cache.get(known_barcode)

        if barcode_data["is_dupe"]:

            self.app.popup_manager.handle_duplicate_barcodes(known_barcode)
        else:
            item_details = self.app.db_manager.get_item_details(barcode=known_barcode)
            if item_details:
                self.process_item_details(item_details)

    def process_item_details(self, item_details):
        item_name = item_details.get("name", "Error!")
        item_price = item_details.get("price", 0.0)
        item_id = item_details.get("item_id")
        self.app.order_manager.add_item(item_name, item_price, item_id=item_id)
        # self.app.order_manager.add_item(item_name, item_price)
        self.app.utilities.update_display()
        self.app.utilities.update_financial_summary()

    def close(self):
        self.stop_thread.set()
        if self.device.is_kernel_driver_active(0):
            self.device.attach_kernel_driver(0)
