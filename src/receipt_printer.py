from datetime import datetime
from escpos.printer import Usb
from PIL import Image
from escpos.config import Config
import textwrap
import base64
import io
import logging
logger = logging.getLogger('rigs_pos')


class ReceiptPrinter:
    def __init__(self, ref, config_path):
        self.config_handler = Config()
        self.config_handler.load(config_path)
        self.app = ref

        try:
            self.printer = self.config_handler.printer()
        except Exception as e:
            logger.warn(e)

    def re_initialize_after_error(self, order_details):
        self.app.utilities.initialize_receipt_printer()
        success = self.print_receipt(order_details)
        if success:
            self.app.popup_manager.receipt_errors_popup.dismiss()
    # https://stackoverflow.com/questions/62848693/how-to-build-a-mddropdownmenu-and-its-items-on-pressing-a-button

    def uuid_to_decimal_string(self, uuid_str):
        uuid_bytes = uuid_str.replace('-', '').encode()
        base64_bytes = base64.b64encode(uuid_bytes)
        return str(base64_bytes.decode('utf-8')).replace('=','')


    def print_receipt(self, order_details, reprint=False, draft=False):
        logger.warn(order_details)
        if len(order_details['items']) == 0:
            return
        try:
            logo = Image.open("images/rigs_logo_scaled.png")
        except Exception as e:
            logger.warn("Error loading logo:", e)

        try:
            self.printer.image(logo, (200, -60))
            date = str(datetime.now().replace(microsecond=0))
            self.printer.set(align="center", font="a")
            self.printer.textln()
            self.printer.textln("402C Main St, Wakefield, RI")
            self.printer.textln("401-363-9866")
            self.printer.textln()
            self.printer.textln()

            max_line_width = 48
            self.printer.set(align="left", font="a", bold=False)

            for item in order_details["items"].values():
                if item["quantity"] > 1:
                    item_name = f"{item['name']} x{item['quantity']}"
                else:
                    item_name = item["name"]
                price = f"${item['total_price']:.2f}"
                spaces = " " * (max_line_width - len(item_name) - len(price))
                item_line = item_name + spaces + price

                self.printer.textln(item_line)
                if float(item['discount']['amount']) > 0:
                    discount_amount = float(item['discount']['amount'])
                    discount_text = f"Discount: -${discount_amount:.2f}"
                    spaces = " " * (max_line_width - len(discount_text))
                    self.printer.textln(spaces + discount_text)

                self.printer.textln()

            self.printer.set(align="right", font="a", bold=True)
            self.printer.textln()

            self.printer.textln(f"Subtotal: ${order_details['subtotal']:.2f}")

            if order_details["discount"] > 0:
                self.printer.textln(f"Discount: -${order_details['discount']:.2f}")

            self.printer.textln(f"Tax: ${order_details['tax_amount']:.2f}")

            self.printer.textln(f"Total: ${order_details['total_with_tax']:.2f}")
            if not draft:
                if order_details["payment_method"] == "Cash":
                    self.printer.textln(
                        f"Cash: ${order_details['amount_tendered']:.2f}"
                    )
                    self.printer.textln(f"Change: ${order_details['change_given']:.2f}")

                elif order_details["payment_method"] == "Split":
                    self.printer.textln("Split Payment")
                elif order_details["payment_method"] == "Debit":
                    self.printer.textln("Debit Payment")
                else:
                    self.printer.textln("Credit Payment")

            # if "split_payments" in locals():
            #     for payment in split_payments:
            #         method = payment["method"]
            #         amount = payment["amount"]
            #         self.printer.textln(f"{method}: ${amount:.2f}")

            self.printer.set(align="center", font="b", bold=False)
            self.printer.textln()

            barcode_data = str(order_details["order_id"])
            short_uuid = barcode_data[:13]  # test truncation length
            barcode_data_short = "{B" + short_uuid
            self.printer.textln(date)
            self.printer.textln(order_details["order_id"])
            if not draft:
                self.printer.barcode(barcode_data_short, "CODE128", pos="OFF")
            if reprint:
                self.printer.set(align="center", font="a", bold=True)
                self.printer.textln()
                self.printer.textln("Copy")
            if draft:
                self.printer.set(align="center", font="a", bold=True)
                self.printer.textln()
                self.printer.textln("UNPAID")

            self.printer.cut()
            return True
        except Exception as e:
            self.app.popup_manager.catch_receipt_printer_errors(e, order_details)
            return False
        # except Exception as e:
        #     self.app.popup_manager.catch_receipt_printer_errors(e, order_details)
        #     return False


    def close(self):
        try:
            self.printer.close()
        except:
            pass
