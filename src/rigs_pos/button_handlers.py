import sys
import re
from open_cash_drawer import open_cash_drawer
from kivy.clock import Clock
from datetime import datetime, timedelta
import time
import inspect

import datetime

import logging
logger = logging.getLogger('rigs_pos')

def log_caller_info(depths=1, to_file=False, filename="caller_info_log.txt"):
    stack = inspect.stack()
    if isinstance(depths, int):
        depths = [depths]

    output_lines = []

    for depth in depths:
        if depth < len(stack):
            caller_frame = stack[depth]
            file_name = caller_frame.filename
            line_number = caller_frame.lineno
            function_name = caller_frame.function
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"{timestamp} - Called from {file_name}, line {line_number}, in {function_name}\n"
            output_lines.append(line)
        else:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"{timestamp} - No caller information available for depth: {depth}\n"
            output_lines.append(line)

    if to_file:

        with open(filename, 'a') as f:
            f.writelines(output_lines)
    else:
        print(''.join(output_lines))


def debounce(wait):
    def decorator(fn):
        last_executed = 0

        def debounced(*args, **kwargs):
            nonlocal last_executed
            current_time = time.time()
            if current_time - last_executed >= wait:
                last_executed = current_time
                return fn(*args, **kwargs)

        return debounced

    return decorator


class ButtonHandler:
    def __init__(self, ref):
        self.app = ref
        self.pin_reset_timer = self.app.pin_reset_timer

    def clear_order(self):
        self.app.order_layout.clear_widgets()
        self.app.order_manager.clear_order()
        self.app.utilities.update_financial_summary()

    # @debounce(0.3)
    def show_reporting(self):
        for i in range(25):
            log_caller_info(depths=i, to_file=True)

        self.app.db_manager.get_order_history()
        self.app.history_popup.show_hist_reporting_popup()

    def show_label_printer_view(self):
        self.app.popup_manager.show_label_printing_view()

    def show_inventory_management_view(self):
        self.app.popup_manager.show_inventory_management_view()

    def show_system_popup(self):
        self.app.popup_manager.show_system_popup()

    def show_calcultor_popup(self):
        self.app.calculator.show_calculator_popup()

    def show_distrib(self):

        self.app.dist_popup.show_dist_reporting_popup()

    def show_dual_pane_mode(self):
        self.app.popup_manager.show_dual_inventory_and_label_managers()

    def show_admin_popup(self):
        self.app.popup_manager.show_admin_popup()

    def show_time_sheets(self):
        self.app.popup_manager.show_attendence_log()

    def show_add_user(self):
        self.app.popup_manager.show_add_user_popup()

    def show_notes_popup(self):
        self.app.popup_manager.show_notes_widget()

    def on_tool_button_press(self, instance):
        tool_actions = {
            "Clear Order": self.clear_order,
            "Open Register": open_cash_drawer,
            "Reporting": self.show_reporting,
            "Label Printer": self.show_label_printer_view,
            "Inventory": self.show_inventory_management_view,
            "System": self.show_system_popup,
            "Calculator": self.show_calcultor_popup,
            "Distrib TEST": self.show_distrib,
            "Dual Pane": self.show_dual_pane_mode,
            "Admin": self.show_admin_popup,
            "Notes": self.show_notes_popup,
        }
        for action_text, action in tool_actions.items():
            if action_text in instance.text:
                action()
                break
        self.app.popup_manager.tools_popup.dismiss()

    def on_admin_button_press(self, instance):
        admin_actions = {
            "Reporting": self.show_reporting,
            "Time Sheets": self.show_time_sheets,
            "Users": self.show_add_user,
        }
        for action_text, action in admin_actions.items():
            if action_text in instance.text:
                action()
                break
        self.app.popup_manager.admin_popup.dismiss()

    def handle_numeric_input(self, input_field, instance_text):
        current_input = (
            input_field.text.replace(".", "")
            .replace("[b]", "")
            .replace("[/b]", "")
            .replace("[size=20]", "")
            .replace("[/size]", "")
        )  # .lstrip("0")
        new_input = current_input + instance_text.replace(".", "").replace(
            "[b]", ""
        ).replace("[/b]", "").replace("[size=20]", "").replace(
            "[/size]", ""
        )  # .lstrip("0")
        new_input = new_input.zfill(2)
        cents = int(new_input)
        dollars = cents // 100
        remaining_cents = cents % 100
        input_field.text = f"{dollars}.{remaining_cents:02d}"

    def on_numeric_button_press(self, instance):
        self.handle_numeric_input(self.app.popup_manager.cash_input, instance.text)

    def on_custom_cash_numeric_button_press(self, instance):
        self.handle_numeric_input(
            self.app.popup_manager.custom_cash_input, instance.text
        )

    def on_split_payment_numeric_button_press(self, instance):
        self.handle_numeric_input(
            self.app.popup_manager.split_payment_numeric_cash_input, instance.text
        )

    def on_split_custom_cash_payment_numeric_button_press(self, instance):
        self.handle_numeric_input(
            self.app.popup_manager.split_custom_cash_input, instance.text
        )

    def on_add_discount_numeric_button_press(self, instance):
        self.handle_numeric_input(
            self.app.popup_manager.discount_amount_input, instance.text
        )

    def on_add_order_discount_numeric_button_press(self, instance):
        self.handle_numeric_input(
            self.app.popup_manager.custom_discount_order_amount_input, instance.text
        )

    def on_adjust_price_numeric_button_press(self, instance):
        self.handle_numeric_input(
            self.app.popup_manager.adjust_price_cash_input, instance.text
        )

    def on_payment_button_press(self, instance):
        payment_actions = {
            "Pay Cash": self.app.popup_manager.show_cash_payment_popup,
            "Pay Debit": self.app.order_manager.handle_debit_payment,
            "Pay Credit": self.app.order_manager.handle_credit_payment,
            "Split": self.app.popup_manager.handle_split_payment,
            "Cancel": lambda: self.app.popup_manager.finalize_order_popup.dismiss(),
        }

        for action_text, action in payment_actions.items():
            if action_text in instance.text:
                action()
                break

    def on_system_button_press(self, instance):
        system_actions = {
            "Reboot System": self.app.popup_manager.reboot_are_you_sure,
            "Restart App": lambda: sys.exit(42),
            "Change Theme": self.app.popup_manager.show_theme_change_popup,
        }

        action = system_actions.get(instance.text)
        if action:
            action()
        self.app.popup_manager.system_popup.dismiss()

    def on_button_press(self, instance):

        button_actions = {
            "Clear Order": self.clear_order,
            "Pay": self.pay_order,
            "Custom": self.show_custom_item_popup,
            "Tools": self.show_tools_popup,
            "Search": self.show_inventory,
        }

        # action = button_actions.get(instance.text)
        # if action:
        #     action()

        for action_text, action in button_actions.items():
            if action_text.lower() in instance.text.lower():
                action()
                break

    def pay_order(self):
        order_count = self.app.order_manager.get_order_details()
        total = self.app.order_manager.calculate_total_with_tax()
        if len(order_count["items"]) > 0:
            if total == 0:
                self.handle_zeroed_orders()
            elif total > 0:
                self.app.order_manager.finalize_order()

    def handle_zeroed_orders(self):
        logger.warn("zeroed")

    def show_custom_item_popup(self):
        self.app.popup_manager.show_custom_item_popup()

    def show_tools_popup(self):
        self.app.popup_manager.show_tools_popup()

    def show_inventory(self):

        self.app.popup_manager.show_inventory()

    def on_done_button_press(self, instance):
        Clock.unschedule(self.app.popup_manager.timeout_event)
        order_details = self.app.order_manager.get_order_details()

        self.app.db_manager.send_order_to_history_database(
            order_details, self.app.order_manager, self.app.db_manager
        )
        self.app.order_manager.clear_order()
        self.app.popup_manager.payment_popup.dismiss()
        self.app.utilities.update_financial_summary()
        self.app.order_layout.clear_widgets()
        self.app.order_manager.delete_order_from_disk(order_details)

    def on_receipt_button_press(self, instance, draft=False):
        printer = self.app.receipt_printer
        order_details = self.app.order_manager.get_order_details()
        if draft:
            printer.print_receipt(order_details, draft=True)
        else:
            printer.print_receipt(order_details)

    def on_lock_screen_button_press(self, button_text, instance):
        if button_text == "Reset":
            self.app.entered_pin = ""
            self.app.popup_manager.pin_input.text = ""
            self.app.pin_reset_timer.reset()
        else:
            self.app.entered_pin += button_text
            self.app.popup_manager.pin_input.text += button_text
            self.app.pin_reset_timer.reset()

        if len(self.app.entered_pin) == 4:
            correct_pin = self.app.utilities.validate_pin(self.app.entered_pin)
            if correct_pin:
                info_dict = correct_pin[0]
                admin = info_dict["admin"]
                # if correct_pin[2] == True:
                if admin:
                    self.app.utilities.cost_overlay_icon.text = (
                        f"[b][size=20]$[/size][/b]"
                    )
                    self.app.admin = True
                else:
                    self.app.utilities.cost_overlay_icon.text = ""
                self.app.utilities.clock_in(self.app.entered_pin)

                self.app.popup_manager.lock_popup.dismiss()
                self.app.is_guard_screen_displayed = False
                self.app.is_lock_screen_displayed = False
                self.app.pin_reset_timer.stop()
                if self.app.popup_manager.disable_lock_screen_checkbox.active:
                    self.app.disable_lock_screen = True
                    reset_time = self.calculate_reset_time()
                    if hasattr(self, "reset_event"):
                        self.reset_event.cancel()

                    self.reset_event = Clock.schedule_once(
                        self.lock_screen_reset, reset_time
                    )
            else:
                self.app.utilities.indicate_incorrect_pin(
                    self.app.popup_manager.lock_popup
                )

                self.app.popup_manager.pin_input.text = ""
                self.app.pin_reset_timer.reset()
            self.app.entered_pin = ""
            self.app.popup_manager.pin_input.text = ""

    def calculate_reset_time(self):
        now = datetime.datetime.now()
        target_time = now.replace(hour=22, minute=0, second=0, microsecond=0)
        if now >= target_time:
            target_time += timedelta(days=1)
        delay = (target_time - now).total_seconds()
        return delay

    def lock_screen_reset(self, *args):
        self.app.disable_lock_screen = False
        self.app.popup_manager.lock_popup.dismiss()
        self.app.popup_manager.guard_popup.dismiss()
        self.app.is_lock_screen_displayed = False
        self.app.is_guard_screen_displayed = False
        self.app.utilities.trigger_guard_and_lock()

    def on_preset_amount_press(self, instance):
        amount = re.sub(r"\[.*?\]", "", instance.text)
        amount = amount.replace("$", "")

        self.app.popup_manager.cash_payment_input.text = amount

    def split_on_preset_amount_press(self, instance):
        amount = re.sub(r"\[.*?\]", "", instance.text)
        amount = amount.replace("$", "")
        self.app.popup_manager.split_cash_input.text = amount
