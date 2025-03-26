import barcode
import textwrap
import json
from barcode.writer import ImageWriter, SVGWriter
from barcode.upc import UniversalProductCodeA as upc_a
from PIL import Image, ImageDraw, ImageFont
import brother_ql
from brother_ql.conversion import convert
from brother_ql.backends.helpers import send
from kivymd.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty, ObjectProperty
from kivy.uix.textinput import TextInput
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.recycleview import RecycleView
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.graphics import Rectangle, Color, Line
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
import threading
from kivy.uix.image import Image as KImage
from io import BytesIO
from kivy.core.image import Image as CoreImage
from kivy.uix.image import Image as KivyImage
import queue
from kivy.clock import Clock
from kivy.app import App
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout

import logging
logger = logging.getLogger('rigs_pos')
class LabelPrintingRow(BoxLayout):
    barcode = StringProperty()
    name = StringProperty()
    price = StringProperty()
    label_printer = ObjectProperty()

    def __init__(self, **kwargs):
        super(LabelPrintingRow, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def add_to_print_queue(self):
        self.show_label_popup()

    def create_focus_popup(
        self, title, content, textinput, size_hint, pos_hint={}, separator_height=1
    ):
        popup = FocusPopup(
            title=title,
            content=content,
            size_hint=size_hint,
            pos_hint=pos_hint,
            separator_height=separator_height,
        )
        popup.focus_on_textinput(textinput)
        return popup

    def show_label_popup(self):
        content = BoxLayout(orientation="vertical")
        quantity_input = TextInput(
            text="1", size_hint=(1, 0.4), input_filter="int", font_size=25
        )
        label_container = MDBoxLayout(size_hint_y=0.1)
        label = Label(text=f"Enter quantity for {self.name}")
        label_container.add_widget(label)
        content.add_widget(label_container)
        content.add_widget(quantity_input)
        btn_layout = BoxLayout(
            orientation="horizontal", size_hint=(0.8, 0.4), spacing=10
        )
        popup = self.create_focus_popup(
            title="",
            content=content,
            textinput=quantity_input,
            size_hint=(0.4, 0.2),
            # pos_hint={"top": 1},
            separator_height=0,
        )

        add_button = MDRaisedButton(
            text="Add",
            size_hint=(0.2, 0.8),
            on_press=lambda x: self.on_add_button_press(quantity_input, popup),
        )

        btn_layout.add_widget(add_button)

        btn_layout.add_widget(
            MDRaisedButton(
                text="Cancel",
                size_hint=(0.2, 0.8),
                on_press=lambda x: popup.dismiss(),
            )
        )
        content.add_widget(btn_layout)

        def on_text(instance, value):

            add_button.disabled = not (value.isdigit() and int(value) > 0)

        quantity_input.bind(text=on_text)

        popup.open()

    def refresh_print_queue_for_embed(self):
        Clock.schedule_once(self.refresh_print_queue_for_embed_main_thread, 0.1)

    def refresh_print_queue_for_embed_main_thread(self, *args):
        try:
            self.app.popup_manager.queue_container.remove_widget(
                self.app.popup_manager.print_queue_embed
            )
            self.app.popup_manager.print_queue_embed = (
                self.app.label_manager.show_print_queue(embed=True)
            )
            self.app.popup_manager.queue_container.add_widget(
                self.app.popup_manager.print_queue_embed
            )
        except Exception as e:
            logger.info(f"Expected error in refresh_print_queue_for_embed\n{e}")

    def on_add_button_press(self, quantity_input, popup):
        self.add_quantity_to_queue(quantity_input.text)
        self.refresh_print_queue_for_embed()
        popup.dismiss()

    def add_quantity_to_queue(self, quantity):
        if quantity.isdigit() and int(quantity) > 0:
            self.label_printer.add_to_queue(
                self.barcode, self.name, self.price, quantity
            )


class LabelPrintingView(BoxLayout):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LabelPrintingView, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, ref, **kwargs):
        if not hasattr(self, "_init"):
            super(LabelPrintingView, self).__init__(**kwargs)
            self.full_inventory = []
            self.app = ref
            self.label_printer = self.app.label_printer
            self.print_queue_ref = LabelPrintingRow()
            self.dual_pane_mode = False

            self._init = True

    def detach_from_parent(self):
        if self.parent:
            self.parent.remove_widget(self)

    def refresh_and_show_print_queue(self):
        try:
            if self.print_queue_popup is not None:
                self.print_queue_popup.dismiss()
            self.show_print_queue()
        except Exception as e:
            logger.info(f"Expected error in refresh_and_show_print_queue")
        self.print_queue_ref.refresh_print_queue_for_embed()

    def update_print_queue_with_label_text(self, item_name, optional_text):
        updated = False
        for item in self.label_printer.print_queue:
            if item["name"] == item_name:
                item["optional_text"] = optional_text
                updated = True
                break
        if updated:
            self.refresh_and_show_print_queue()

    def clear_search(self):
        self.ids.label_search_input.text = ""

    def show_inventory_for_label_printing(self, inventory_items, dual_pane_mode=False):

        self.full_inventory = inventory_items
        self.ids.label_rv.data = self.generate_data_for_rv(
            inventory_items, self.dual_pane_mode
        )

    def remove_from_queue(self, item_name, embed=False):
        removed, is_empty = self.label_printer.remove_from_queue(item_name)
        if removed:
            if is_empty:
                if embed:
                    self.print_queue_ref.refresh_print_queue_for_embed()
                else:
                    self.print_queue_popup.dismiss()

            else:
                if embed:
                    self.print_queue_ref.refresh_print_queue_for_embed()
                else:
                    self.print_queue_popup.dismiss()
                    self.show_print_queue()

    def update_search_input(self, barcode):
        self.ids.label_search_input.text = barcode

    def handle_scanned_barcode(self, barcode):
        barcode = barcode.strip()
        items = self.app.db_manager.get_all_items()

        if any(item[0] == barcode for item in items):
            Clock.schedule_once(lambda dt: self.update_search_input(barcode), 0.1)
            return

        for item in items:
            if (
                item[0][1:] == barcode
                or item[0] == barcode[:-4]
                or item[0][1:] == barcode[:-4]
            ):
                Clock.schedule_once(lambda dt: self.update_search_input(item[0]), 0.1)
                return

    def show_print_queue(self, embed=False):

        queue_layout = BoxLayout(orientation="vertical", spacing=5, padding=5)
        item_layout = BoxLayout(orientation="vertical", spacing=5, padding=5)
        for item in self.label_printer.print_queue:
            if embed:
                if len(item["name"]) > 30:
                    name_label = Label(text=f"{item['name'][:27]}...", size_hint_x=0.2)
                else:
                    name_label = Label(text=f"{item['name']}", size_hint_x=0.2)
            else:
                name_label = Label(text=f"{item['name']}", size_hint_x=0.2)
            logger.warn(name_label)
            qty_label = Label(text=f"Qty: {item['quantity']}", size_hint_x=0.05)
            text_label = Label(
                text=f"Text: {item['optional_text']}", size_hint_x=0.2, halign="left"
            )
            if embed:
                plus_button = MDIconButton(
                    icon="plus",
                    on_press=lambda x, item=item: self.increment_quantity(
                        item_str=item["name"], embed=True
                    ),
                    size_hint_x=0.1,
                )
                minus_button = MDIconButton(
                    icon="minus",
                    on_press=lambda x, item=item: self.decrement_quantity(
                        item_str=item["name"], embed=True
                    ),
                    size_hint_x=0.1,
                )
                rm_button = Button(
                    text="Remove",
                    on_press=lambda x, item=item: self.remove_from_queue(
                        item_name=item["name"], embed=True
                    ),
                    size_hint_x=0.1,
                )
            else:
                plus_button = MDIconButton(
                    icon="plus",
                    on_press=lambda x, item=item: self.increment_quantity(
                        item_str=item["name"]
                    ),
                    size_hint_x=0.1,
                )
                minus_button = MDIconButton(
                    icon="minus",
                    on_press=lambda x, item=item: self.decrement_quantity(
                        item_str=item["name"]
                    ),
                    size_hint_x=0.1,
                )

                rm_button = Button(
                    text="Remove",
                    on_press=lambda x, item=item: self.remove_from_queue(
                        item_name=item["name"]
                    ),
                    size_hint_x=0.1,
                )
            text_button = Button(
                text="Add Text",
                on_press=lambda x, item=item: self.add_label_text(
                    item_str=item["name"]
                ),
                size_hint_x=0.1,
            )
            preview_button = Button(
                text="Preview",
                on_press=lambda x, item=item: self.label_printer.preview_barcode_label(
                    name=item["name"]
                ),
                size_hint_x=0.1,
            )
            item_row = GridLayout(cols=8, spacing=5, size_hint_y=None, height=40)
            item_row.add_widget(name_label)
            item_row.add_widget(qty_label)
            item_row.add_widget(text_label)
            item_row.add_widget(plus_button)
            item_row.add_widget(minus_button)
            item_row.add_widget(text_button)
            item_row.add_widget(preview_button)
            item_row.add_widget(rm_button)
            item_layout.add_widget(item_row)
            line = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=1)
            line.md_bg_color = (0.56, 0.56, 1, 1)

            item_layout.add_widget(line)

        btn_layout = BoxLayout(
            orientation="horizontal", spacing=5, padding=5, size_hint_y=0.2
        )
        btn_layout.add_widget(
            MDRaisedButton(
                text=f"[b][size=20]Print Now[/size][/b]",
                on_press=self.print_now,
                size_hint=(0.2, 1),
            )
        )
        btn_layout.add_widget(BoxLayout(size_hint_x=0.2))
        if embed:
            pass
        else:
            btn_layout.add_widget(
                MDFlatButton(
                    text="Cancel",
                    on_press=self.cancel_print,
                    size_hint=(0.1, 1),
                    md_bg_color="grey",
                )
            )
        if embed:
            btn_layout.add_widget(
                MDFlatButton(
                    text="Clear Queue",
                    on_press=lambda x: self.clear_queue(embed=True),
                    size_hint=(0.1, 1),
                    md_bg_color="grey",
                )
            )
        else:
            btn_layout.add_widget(
                MDFlatButton(
                    text="Clear Queue",
                    on_press=lambda x: self.clear_queue(embed=False),
                    size_hint=(0.1, 1),
                    md_bg_color="grey",
                )
            )

        queue_layout.add_widget(item_layout)
        queue_layout.add_widget(btn_layout)
        if embed:
            return queue_layout
        else:
            self.print_queue_popup = Popup(
                title="Print Queue",
                content=queue_layout,
                size_hint=(0.8, 0.6),
            )

            self.print_queue_popup.open()

    def add_label_text(self, item_str):
        add_lable_layout = BoxLayout(orientation="vertical", size_hint_y=1)
        add_label_text_layout = BoxLayout(orientation="vertical", size_hint_y=0.5)
        name_truncated = item_str[:15]
        # add_label_text_label = Label(text="15 Characters Max")
        self.add_label_text_input = TextInput(
            text=name_truncated, size_hint=(1, 0.1), multiline=False
        )
        # add_label_text_layout.add_widget(add_label_text_label)
        add_label_text_layout.add_widget(self.add_label_text_input)
        add_label_button_layout = BoxLayout(
            orientation="horizontal", spacing=5, size_hint=(1, 0.5)
        )
        add_label_confirm_button = MDRaisedButton(
            text="Confirm",
            on_press=lambda x: self.on_add_label_confirm_button_press(item_str),
            size_hint=(1, 1),
        )
        add_label_cancel_button = MDRaisedButton(
            text="Cancel",
            on_press=lambda x: self.add_label_popup.dismiss(),
            size_hint=(1, 1),
        )
        add_label_button_layout.add_widget(add_label_confirm_button)
        add_label_button_layout.add_widget(add_label_cancel_button)
        add_lable_layout.add_widget(add_label_text_layout)
        add_lable_layout.add_widget(add_label_button_layout)
        self.add_label_popup = self.create_focus_popup(
            title="Add Text to Selected Label",
            content=add_lable_layout,
            textinput=self.add_label_text_input,
            # pos_hint={"top": 1},
            size_hint=(0.4, 0.2),
        )
        self.add_label_popup.open()

    def on_add_label_confirm_button_press(self, item_str):
        self.add_label_popup.dismiss()
        for item in self.label_printer.print_queue:
            if item_str == item["name"]:
                item["optional_text"] = self.add_label_text_input.text
                self.label_printer.save_queue()
                self.refresh_and_show_print_queue()
                break

    def increment_quantity(self, item_str, embed=False):
        for item in self.label_printer.print_queue:
            if item["name"] == item_str:
                item["quantity"] += 1
                self.label_printer.save_queue()
                if embed:
                    self.print_queue_ref.refresh_print_queue_for_embed()
                else:
                    self.refresh_and_show_print_queue()
                break

    def decrement_quantity(self, item_str, embed=False):
        for item in self.label_printer.print_queue:
            if item["name"] == item_str:
                if item["quantity"] > 1:
                    item["quantity"] -= 1
                    self.label_printer.save_queue()
                    if embed:
                        self.print_queue_ref.refresh_print_queue_for_embed()
                    else:
                        self.refresh_and_show_print_queue()
                    break

    def update_print_queue_quantity(self, item_name, new_quantity):
        self.label_printer.update_queue_item_quantity(item_name, new_quantity)
        self.label_printer.save_queue()

    def clear_queue(self, embed=False):
        self.label_printer.clear_queue()
        self.label_printer.save_queue()
        if embed:
            self.print_queue_ref.refresh_print_queue_for_embed()
        else:
            self.print_queue_popup.dismiss()

    def print_now(self, instance):
        self.label_printer.process_queue()

    def cancel_print(self, instance):
        self.print_queue_popup.dismiss()

    def generate_data_for_rv(self, items, dual_pane_mode=False):
        data = []
        if self.dual_pane_mode:
            for item in items:
                if len(str(item[1])) > 80:

                    data.append(
                        {
                            "barcode": str(item[0]),
                            "name": f"{item[1][:77]}...",
                            "price": (
                                f"{float(item[2]):.2f}" if item[2] else "Not Found"
                            ),
                            "label_printer": self.label_printer,
                        }
                    )
                else:

                    data.append(
                        {
                            "barcode": str(item[0]),
                            "name": item[1],
                            "price": (
                                f"{float(item[2]):.2f}" if item[2] else "Not Found"
                            ),
                            "label_printer": self.label_printer,
                        }
                    )
            return data
        else:
            for item in items:
                data.append(
                    {
                        "barcode": str(item[0]),
                        "name": item[1],
                        "price": f"{float(item[2]):.2f}" if item[2] else "Not Found",
                        "label_printer": self.label_printer,
                    }
                )
            return data

    def filter_inventory(self, query="", dual_pane_mode=False):
        filtered_items = (
            self.full_inventory
            if not query
            else [
                item
                for item in self.full_inventory
                if query.lower() in str(item[0]).lower()
                or query.lower() in item[1].lower()
            ]
        )
        display_data = self.generate_data_for_rv(
            filtered_items, dual_pane_mode=dual_pane_mode
        )
        self.ids.label_rv.data = display_data

    def create_focus_popup(
        self, title, content, textinput, size_hint, pos_hint={}, separator_height=1
    ):
        popup = FocusPopup(
            title=title,
            content=content,
            size_hint=size_hint,
            pos_hint=pos_hint,
            separator_height=separator_height,
        )
        popup.focus_on_textinput(textinput)
        return popup


class LabelPrinter:
    def __init__(self, ref):
        self.print_queue = []
        self.app = ref
        self.print_queue_ref = LabelPrintingRow()
        self.queue_file_path = "print_queue.json"
        self.load_queue()

    def save_queue(self):

        try:
            with open(self.queue_file_path, "w") as file:
                json.dump(self.print_queue, file)
        except Exception as e:
            logger.warn(f"Error saving print queue: {e}")

    def load_queue(self):

        try:
            with open(self.queue_file_path, "r") as file:
                self.print_queue = json.load(file)
        except FileNotFoundError:

            self.print_queue = []
        except Exception as e:
            logger.warn(f"Error loading print queue: {e}")

    def add_to_queue(self, barcode, name, price, quantity):
        try:
            self.print_queue.append(
                {
                    "barcode": barcode,
                    "name": name,
                    "price": price,
                    "quantity": int(quantity),
                    "optional_text": "",
                }
            )
            self.save_queue()
        except Exception as e:
            logger.warn(f"Error adding labels to the queue. Probably tried to add 0 \n{e}")

    def update_queue_item_quantity(self, name, new_quantity):
        for item in self.print_queue:
            if item["name"] == name:
                item["quantity"] = new_quantity
                self.save_queue()
                break

    def clear_queue(self):
        self.print_queue.clear()
        self.save_queue()

    def calculate_dynamic_font_size(
        self,
        draw,
        text,
        max_width,
        start_font_size=40,
        min_font_size=10,
        font_path="/usr/share/fonts/TTF/Arial.TTF",
    ):
        font_size = start_font_size
        font = ImageFont.truetype(font_path, font_size)
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]

        while text_width > max_width and font_size > min_font_size:
            font_size -= 1
            font = ImageFont.truetype(font_path, font_size)
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]

        return font_size

    def preview_barcode_label(self, name):
        for i in self.print_queue:
            if i["name"] == name:
                try:
                    logger.warn(int(i["barcode"]))
                except ValueError as e:
                    logger.warn("probably no barcode")
                    self.app.popup_manager.catch_label_printer_missing_barcode()
                    break
                if len(i["optional_text"]) > 0:
                    label_image = self.print_barcode_label(
                        i["barcode"],
                        i["price"],
                        optional_text=i["optional_text"],
                        include_text=True,
                        preview=True,
                    )
                    self.open_preview_popup(label_image)
                    break
                else:
                    label_image = self.print_barcode_label(
                        i["barcode"], i["price"], preview=True
                    )
                    self.open_preview_popup(label_image)
                    break

    def open_preview_popup(self, label_image):

        blank_image = Image.open("images/blank_label.png")
        label_image = label_image.convert("RGBA")
        blank_image = blank_image.convert("RGBA")
        blank_width, blank_height = blank_image.size
        label_width, label_height = label_image.size
        x_position = (blank_width - label_width) // 2
        y_position = (blank_height - label_height) // 2

        blank_image.paste(label_image, (x_position, y_position), label_image)
        data = BytesIO()
        blank_image.save(data, format="PNG")
        data.seek(0)

        core_image = CoreImage(data, ext="png")
        kivy_image = KivyImage(texture=core_image.texture)
        layout = BoxLayout(orientation="vertical")
        layout.add_widget(kivy_image)

        self.preview_popup = Popup(
            content=layout,
            size_hint=(0.2, 0.2),
            title="",
            background="images/transparent.png",
            background_color=(0, 0, 0, 0),
            separator_height=0,
        )

        self.preview_popup.open()

    def debug_dimensions(self, barcode_image):
        logger.warn("Barcode size:", barcode_image.size)
        logger.warn("Label size: (202, 202)")
        logger.warn("Barcode position on label:", ((202 - barcode_image.size[0]) // 2, 35))

    def print_barcode_label(
        self,
        barcode_data,
        item_price,
        save_path=None,
        include_text=False,
        optional_text="",
        preview=False,
    ):
        logger.warn(type(barcode_data))
        label_width, label_height = 202, 202
        barcode_y_position = 35

        UPC = barcode.get_barcode_class("upc")

        writer = ImageWriter()
        try:
            logger.warn(f"we have upc a:\n'{barcode_data}")
            upc = UPC(barcode_data, writer=writer)
        except barcode.errors.NumberOfDigitsError as e:
            logger.warn(f"we have upc e:\n'{barcode_data}")
            upc = UPC(self.handle_upc_e(barcode_data), writer=writer)
        except barcode.errors.IllegalCharacterError as e:
            logger.info(f"probably no barcode or something unexpected{barcode_data}")
            self.app.popup_manager.catch_label_printer_missing_barcode()
        barcode_image = upc.render(
            {
                "module_width": 0.17,
                "module_height": 10 if not include_text else 8,
                # "font_size": 2,
                "dpi": 300,
                "write_text": False,
                "quiet_zone": 0,
            }
        )

        label_image = Image.new("RGB", (label_width, label_height), "white")
        draw = ImageDraw.Draw(label_image)

        font_size = 33
        font = ImageFont.truetype("/usr/share/fonts/TTF/Arialbd.TTF", font_size)
        text = f"${item_price}"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x_text = (label_width - text_width) / 2
        draw.text((x_text, 0), text, fill="black", font=font)

        barcode_width, barcode_height = barcode_image.size

        barcode_position = ((label_width - barcode_width) // 2, barcode_y_position)

        label_image.paste(barcode_image, barcode_position)

        if include_text and optional_text:
            max_optional_text_width = label_width
            additional_text_font_size = self.calculate_dynamic_font_size(
                draw, optional_text, max_optional_text_width
            )
            additional_font = ImageFont.truetype(
                "/usr/share/fonts/TTF/Arial.TTF", additional_text_font_size
            )

            additional_text_bbox = draw.textbbox(
                (0, 0), optional_text, font=additional_font
            )
            additional_text_width = additional_text_bbox[2] - additional_text_bbox[0]
            x_additional_text = (label_width - additional_text_width) / 2
            additional_text_y_position = barcode_y_position + barcode_height  # + 10
            draw.text(
                (x_additional_text, additional_text_y_position),
                optional_text,
                fill="black",
                font=additional_font,
            )
        if preview:
            return label_image
        else:
            qlr = brother_ql.BrotherQLRaster("QL-710W")
            qlr.exception_on_warning = True
            convert(qlr=qlr, images=[label_image], label="23x23", cut=False)
            try:
                send(
                    instructions=qlr.data,
                    printer_identifier="usb://0x04F9:0x2043",
                    backend_identifier="pyusb",
                )
                return True
            except Exception as e:
                self.catch_label_printing_errors(e)
                return False

    def catch_label_printing_errors(self, e):
        Clock.schedule_once(
            lambda dt: self.app.popup_manager.catch_label_printing_errors(e), 0
        )

    def handle_upc_e(self, barcode_data):
        logger.warn(f"inside handle_upc_e:\n'{barcode_data}")
        padding = 12 - len(barcode_data)
        upc = barcode_data + "0" * padding
        logger.warn(upc)
        return upc

    def process_queue(self):
        print_thread = threading.Thread(
            target=self._process_print_queue_thread, daemon=True
        )

        print_thread.start()

    def _process_print_queue_thread(self):
        self.print_success = True
        for item in self.print_queue:
            item_quantity = item.get("quantity", 1)
            for _ in range(item_quantity):
                success = self.print_barcode_label(
                    barcode_data=item["barcode"],
                    item_price=item["price"],
                    include_text="optional_text" in item
                    and item["optional_text"] != "",
                    optional_text=item.get("optional_text", ""),
                )
                if not success:

                    self.print_success = False
                    break
            if not self.print_success:
                break

        if self.print_success:
            self.print_queue.clear()
            self.save_queue()
            self.print_queue_ref.refresh_print_queue_for_embed()
            try:
                self.app.label_manager.print_queue_popup.dismiss()
            except Exception as e:
                logger.info(f"Expected error dismissing print queue popup\n{e}")
            try:
                self.app.popup_manager.label_errors_popup.dismiss()
            except Exception as e:
                logger.info(f"Expected error dismissing error popup:\n {e}")

    def remove_from_queue(self, name):
        for i, item in enumerate(self.print_queue):
            if item["name"] == name:
                self.print_queue.pop(i)
                self.save_queue()
                return True, len(self.print_queue) == 0
        return False, False


class PrintQueueRow(BoxLayout):
    name = StringProperty()
    quantity = StringProperty()
    remove_callback = ObjectProperty()
    quantity_changed_callback = ObjectProperty()
    add_label_text_callback = ObjectProperty()
    preview_barcode_label_callback = ObjectProperty()
    optional_text = StringProperty()

    def __init__(self):
        self.label_printer = LabelPrinter()

    def on_remove_button_press(self):
        if self.remove_callback:
            self.remove_callback(self.name)

    def on_add_label_confirm_button_press(self):
        optional_text = self.add_label_text_input.text

        if self.add_label_text_callback:
            self.add_label_text_callback(self.name, optional_text)
        self.add_label_popup.dismiss()

    def preview_barcode_label(self):
        if self.preview_barcode_label_callback:
            self.preview_barcode_label_callback(self.name)


class LabelQueueLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(LabelQueueLayout, self).__init__(**kwargs)

        # self.bind(children=self.update_height)

        self.orientation = "vertical"
        # self.height = self.minimum_height

    # def update_height(self, *args):
    #     self.height = len(self.children) * dp(48)


class FocusPopup(Popup):
    def focus_on_textinput(self, textinput):
        self.textinput_to_focus = textinput

    def on_open(self):
        if hasattr(self, "textinput_to_focus"):
            self.textinput_to_focus.focus = True


if __name__ == "__main__":
    printer = LabelPrinter()
    printer.print_barcode_label("123456789012", 9.99, "test.png")
