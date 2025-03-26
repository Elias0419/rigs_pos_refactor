import subprocess
import time
import sys
import json
import logging

logger = logging.getLogger('wrapper')
wrapper_logging_configured = False

def setup_logging():

    global wrapper_logging_configured
    if not wrapper_logging_configured:
        logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler('wrapper.log')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S'
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter_console = logging.Formatter(
            '%(name)-12s: %(levelname)-8s %(message)s'
        )
        ch.setFormatter(formatter_console)
        logger.addHandler(ch)

        logger.propagate = False
        wrapper_logging_configured = True

setup_logging()

class Wrapper:
    def __init__(self):
        logger.info("""\n
        APPLICATION START
        \n""")

        self.DEFAULT_CONFIG = {
            "script_path": "/home/rigs/rigs_pos/main.py",
            "recipient": "info@example.com",
        }
        self.config = self.load_config()
        self.crash_count = 0
        self.max_crashes = 3

    def load_config(self):
        try:
            with open("/home/rigs/rigs_pos/wrapper_config.json", "r") as f:
                config = json.load(f)
        except Exception:
            logger.warning("Could not load /home/rigs/rigs_pos/wrapper_config.json; using defaults.")
            config = self.DEFAULT_CONFIG
        return config

    def run_app(self):
        while True:
            process = subprocess.Popen([
                "/home/rigs/0/bin/python3",
                self.config["script_path"]
            ])
            ret_code = process.wait()

            if ret_code == 42:
                logger.info("Received admin code 42. Stopping wrapper loop.")
                break
            else:
                self.crash_count += 1
                logger.warning(f"Application ended with returncode {ret_code}. Crash count: {self.crash_count}")

                # If crash count hits the threshold, send email and reboot.
                if self.crash_count >= self.max_crashes:
                    self.send_email(
                        subject="Application Crash Alert",
                        message=(
                            f"The application has crashed {self.crash_count} times.\n"\
                            "Initiating system reboot."
                        ),
                        recipient=self.config["recipient"]
                    )
                    logger.error("Max crash count reached. Rebooting the system now.")

                    try:
                        subprocess.run(["reboot"], check=True)
                    except Exception as e:
                        logger.error(f"Failed to reboot: {e}")
                        sys.exit(1)


    def send_email(self, subject, message, recipient):

        email_content = f"{subject}\n\n{message}"
        try:
            subprocess.run(
                ["msmtp", recipient],
                input=email_content,
                text=True,
                check=True
            )
            logger.info("Crash notification email sent.")
        except Exception as e:
            logger.warning(f"Failed to send email: {e}")

if __name__ == "__main__":
    wrapper = Wrapper()
    wrapper.run_app()
